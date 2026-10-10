"""Construit le `RapportSandbox` à partir des journaux du traceur et du piège réseau.

Les journaux sont des DONNÉES écrites en partie par le paquet analysé : chaque ligne est validée,
bornée en taille et en nombre ; une ligne illisible est ignorée. Le rapport ne fait que constater.
"""

import base64
import json
import re
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
# Un journal réseau tronqué (déluge de requêtes) est lui-même une requête suspecte (B, C1).
JOURNAL_TRONQUE = "(journal réseau tronqué : déluge de requêtes)"
# Traces effacées ou réécrites : une marque de début ou de fin, avec le jeton secret de l'analyse,
# manque dans un journal (B, C2). Mise en tête des processus, pour la politique de B.
TRACES_EFFACEES = "(traces de la sandbox effacées ou réécrites par le paquet)"
# Commandes que pip lance lui-même pendant l'installation : détection de la plateforme, et les
# crochets de construction d'un sdist (le code de setup.py, lui, reste visible : fichiers, réseau,
# et tout processus qu'il lance).
PROCESSUS_DE_PIP = ("lsb_release -a", "uname -rs")
CROCHETS_DE_PIP = re.compile(r"^/usr/local/bin/python /usr/local/lib/python3\.\d+/site-packages/pip/"
                             r"_vendor/pyproject_hooks/_in_process/_in_process\.py "
                             r"(get_requires_for_build_wheel|prepare_metadata_for_build_wheel|"
                             r"build_wheel) /tmp/tmp\w+$")


def _de_pip(commande: str) -> bool:
    return commande in PROCESSUS_DE_PIP or bool(CROCHETS_DE_PIP.match(commande))


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


# --- v2 : lignes de `strace -f -e trace=openat,execve,connect` -------------------------------------
# Elles voient aussi le code natif et ctypes, que le traceur Python ne voit pas.
_ST_OPENAT = re.compile(r'^\d+\s+openat\([^,]+, "((?:[^"\\]|\\.)*)", [^)]*\) = (\d+)')
_ST_EXECVE = re.compile(r'^\d+\s+execve\("[^"]*", \[(.*?)\](?:\.\.\.)?, .*\) = 0')
_ST_CONNECT = re.compile(r'^\d+\s+connect\(\d+, \{sa_family=AF_INET6?, sin6?_port=htons\((\d+)\), '
                         r'(?:sin_addr=inet_addr\("([^"]+)"\)|.*?inet_pton\(AF_INET6, "([^"]+)")')
_ST_ARG = re.compile(r'"((?:[^"\\]|\\.)*)"')
# Les commandes de l'analyse elle-même (pas celles du paquet).
_ST_RACINES = ("/outils/importer.py", "-m pip install")


def _strace(lignes: Iterable[str]) -> list[tuple[str, str]]:
    """[(sorte, valeur)] : ("open", chemin ouvert avec succès), ("processus", commande),
    ("connect", "ip:port")."""
    sortie = []
    for ligne in lignes:
        if not isinstance(ligne, str):
            continue
        if (m := _ST_OPENAT.match(ligne)):
            sortie.append(("open", m.group(1)))
        elif (m := _ST_EXECVE.match(ligne)):
            commande = " ".join(_ST_ARG.findall(m.group(1)))
            if not any(r in commande for r in _ST_RACINES):
                sortie.append(("processus", commande))
        elif (m := _ST_CONNECT.match(ligne)):
            sortie.append(("connect", f"{m.group(2) or m.group(3)}:{m.group(1)}"))
    return sortie


def _traces_intactes(trace: list[str], strace_installation: list[str], strace_import: list[str],
                     jeton: str) -> bool:
    """Chaque journal porte les marques que lancer.sh y écrit avec le jeton (inconnu du paquet)."""
    marques = {(e.get("e"), e.get("v")) for e in _lignes(trace)}
    fin_strace = f"SAS-FIN {jeton}"
    return (("debut", jeton) in marques and ("fin", jeton) in marques
            and fin_strace in strace_installation and fin_strace in strace_import)


def construire(trace: Iterable[str], reseau: Iterable[str], leurres: dict[str, str], home: str,
               code_sortie: int, duree_s: float, delai_depasse: bool,
               ip_piege: str | None = None, strace_installation: Iterable[str] = (),
               strace_import: Iterable[str] = (), jeton: str | None = None) -> RapportSandbox:
    trace, strace_installation, strace_import = list(trace), list(strace_installation), list(strace_import)
    dns, connexions, fichiers, lus, processus = _Liste(), _Liste(), _Liste(), _Liste(), _Liste()
    textes_reseau: list[str] = []      # ce qui est sorti du conteneur : on y cherche les leurres
    vues_par_le_piege: list[str] = []

    for e in _lignes(reseau):
        if e.get("t") == "tronque":
            dns.insert(0, JOURNAL_TRONQUE)
            continue
        if e.get("t") == "dns" and (nom := _texte(e.get("nom"))):
            textes_reseau.append(nom)
            if not _local(nom):
                dns.ajouter(nom.rstrip("."))
        elif e.get("t") == "tcp" and isinstance(e.get("port"), int):
            hote = _texte(e.get("hote"))
            debut = e.get("debut") if isinstance(e.get("debut"), str) else ""
            textes_reseau.extend([hote or "", debut])
            vues_par_le_piege.append(f"{hote or ip_piege or '?'}:{e['port']}")

    # Le piège d'abord (hors de portée du paquet), le traceur ensuite : le paquet ne peut pas
    # remplir la liste jusqu'au plafond avant que la vraie connexion y entre (B, C7).
    for cnx in vues_par_le_piege:
        connexions.ajouter(cnx)

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
            if not (e.get("p") == "installation" and _de_pip(v)):
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

    for phase, lignes in (("installation", strace_installation), ("import", strace_import)):
        for sorte, v in _strace(lignes):
            v = v[:MAX_TEXTE]
            if sorte == "open" and (sensible := _sensible(v, home)):
                fichiers.ajouter(sensible)
                if sensible[2:] in FICHIERS_LEURRES:
                    lus.ajouter(sensible)
            elif sorte == "processus" and not (phase == "installation" and _de_pip(v)):
                processus.ajouter(v)
            elif sorte == "connect":
                hote = v.rsplit(":", 1)[0]
                if not _local(hote) and hote != ip_piege:
                    connexions.ajouter(v)

    tout = "\n".join(textes_reseau)
    for nom, secret in leurres.items():
        if any(f in tout or f in tout.lower() for f in _formes(secret)):
            lus.ajouter(f"{nom} (exfiltré)")

    if jeton and not delai_depasse and not _traces_intactes(trace, strace_installation,
                                                              strace_import, jeton):
        processus.insert(0, TRACES_EFFACEES)

    return RapportSandbox(requetes_dns=list(dns), connexions=list(connexions),
                          fichiers_sensibles=list(fichiers), leurres_lus=list(lus),
                          processus=list(processus), code_sortie=code_sortie,
                          duree_s=round(duree_s, 2), delai_depasse=delai_depasse)
