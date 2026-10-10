"""Construit le `RapportSandbox` à partir des journaux du traceur et du piège réseau.

Les journaux sont des DONNÉES écrites en partie par le paquet analysé : chaque ligne est validée,
bornée en taille et en nombre ; une ligne illisible est ignorée. Le rapport ne fait que constater.
"""

import base64
import json
from collections.abc import Iterable

from commun.modeles import RapportSandbox

MAX_ENTREES = 100
MAX_TEXTE = 300

# Chemins sensibles, relatifs au HOME du conteneur, puis absolus.
SENSIBLES_HOME = (".ssh/", ".aws/", ".npmrc", ".pypirc", ".git-credentials", ".netrc",
                  ".docker/config.json", ".kube/config", ".bash_history", ".gnupg/", ".config/gh/")
SENSIBLES_ABSOLUS = ("/etc/shadow", "/etc/passwd", "/etc/sudoers", "/root/")
# Fichiers leurres que la sandbox pose dans le HOME.
FICHIERS_LEURRES = (".aws/credentials", ".ssh/id_rsa", ".npmrc", ".pypirc", ".git-credentials")
NOMS_LOCAUX = ("localhost", "ip6-localhost", "")


def _lignes(lignes: Iterable[str]) -> list[dict]:
    sortie = []
    for ligne in lignes:
        try:
            e = json.loads(ligne)
        except (ValueError, TypeError):
            continue
        if isinstance(e, dict):
            sortie.append(e)
    return sortie


def _texte(v) -> str | None:
    return v[:MAX_TEXTE] if isinstance(v, str) and v else None


class _Liste(list):
    def ajouter(self, v: str | None) -> None:
        if v and v not in self and len(self) < MAX_ENTREES:
            self.append(v)


def _local(hote: str) -> bool:
    return hote.rstrip(".") in NOMS_LOCAUX or hote.startswith("127.") or hote == "::1"


def _formes(secret: str) -> list[str]:
    """Le secret tel quel, en hexadécimal et en base64 (trois alignements)."""
    brut = secret.encode()
    formes = [secret.lower(), brut.hex()]
    for k in range(3):
        b64 = base64.b64encode(b"\0" * k + brut).decode()
        formes.append(b64[4:-4])
    return [f for f in formes if len(f) >= 8]


def _sensible(chemin: str, home: str) -> str | None:
    if chemin.startswith(home.rstrip("/") + "/"):
        relatif = chemin[len(home.rstrip("/")) + 1:]
        if relatif.startswith(SENSIBLES_HOME):
            return "~/" + relatif
    if chemin.startswith(SENSIBLES_ABSOLUS) or (chemin.startswith("/proc/")
                                                 and chemin.endswith("/environ")):
        return chemin
    return None


def construire(trace: Iterable[str], reseau: Iterable[str], leurres: dict[str, str], home: str,
               code_sortie: int, duree_s: float, delai_depasse: bool,
               ip_piege: str | None = None) -> RapportSandbox:
    dns, connexions, fichiers, lus, processus = _Liste(), _Liste(), _Liste(), _Liste(), _Liste()
    textes_reseau: list[str] = []      # ce qui est sorti du conteneur : on y cherche les leurres
    vues_par_le_piege: list[str] = []

    for e in _lignes(reseau):
        if e.get("t") == "dns" and (nom := _texte(e.get("nom"))):
            textes_reseau.append(nom)
            if not _local(nom):
                dns.ajouter(nom.rstrip("."))
        elif e.get("t") == "tcp" and isinstance(e.get("port"), int):
            hote = _texte(e.get("hote"))
            debut = e.get("debut") if isinstance(e.get("debut"), str) else ""
            textes_reseau.extend([hote or "", debut])
            vues_par_le_piege.append(f"{hote or ip_piege or '?'}:{e['port']}")

    for e in _lignes(trace):
        sorte, v = e.get("e"), _texte(e.get("v"))
        if not v:
            continue
        if sorte == "open":
            if (s := _sensible(v, home)):
                fichiers.ajouter(s)
                if s[2:] in FICHIERS_LEURRES:
                    lus.ajouter(s)
        elif sorte == "processus":
            processus.ajouter(v)
        elif sorte == "dns":
            hote = v.rsplit(":", 1)[0]
            if not _local(hote):
                dns.ajouter(hote)
                connexions.ajouter(v)
        elif sorte == "connect":
            hote = v.rsplit(":", 1)[0]
            if not _local(hote) and hote != ip_piege:
                connexions.ajouter(v)

    for cnx in vues_par_le_piege:
        connexions.ajouter(cnx)

    tout = "\n".join(textes_reseau)
    for nom, secret in leurres.items():
        if any(f in tout or f in tout.lower() for f in _formes(secret)):
            lus.ajouter(f"{nom} (exfiltré)")

    return RapportSandbox(requetes_dns=list(dns), connexions=list(connexions),
                          fichiers_sensibles=list(fichiers), leurres_lus=list(lus),
                          processus=list(processus), code_sortie=code_sortie,
                          duree_s=round(duree_s, 2), delai_depasse=delai_depasse)
