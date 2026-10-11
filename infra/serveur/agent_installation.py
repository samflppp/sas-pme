#!/usr/bin/env python3
"""Agent d'installation du serveur de démo (A pour C, conception-demo § 1).

Il lit au guichet de la passerelle (:8444) les demandes d'installation de la plateforme et lance
`pip install --upgrade <nom>` vers la passerelle seulement. Le serveur reçoit donc la dernière
version vérifiée, jamais la dernière publiée sur Internet.

Il ne croit pas le guichet : chaque demande est vérifiée ici, avec la clé publique de la plateforme
(Ed25519, octets préfixés comme dans passerelle/installation.py), puis l'âge (10 min au plus), le
nonce (une seule fois, même après redémarrage) et le nom (PEP 508, jamais une option de pip).
Autonome : seule dépendance, `cryptography`. Réglages :
  SAS_GUICHET_URL     http://10.42.2.10:8444
  SAS_INDEX_URL       http://10.42.2.10:8080/simple/
  SAS_CLE_PUBLIQUE    clé publique de la plateforme (PEM), posée à l'installation
  SAS_AGENT_ETAT      dossier de l'agent (défaut /var/lib/sas-agent) : dernier rang lu, nonces vus
  SAS_AGENT_INTERVALLE  secondes entre deux lectures (défaut 2)
  SAS_AGENT_PYTHON    Python de l'environnement où installer (défaut : celui de l'agent) ; sur AWS,
                      le venv applicatif du serveur (~/app), l'agent tournant avec le Python du système
  SAS_AGENT_REESSAI   secondes entre deux essais d'un pip qui a échoué (défaut 20)
  SAS_AGENT_PATIENCE  minutes pendant lesquelles on réessaie (défaut 30)

Une demande arrive avant que sa version soit servie : la plateforme doit encore l'attendre et
l'analyser. Un pip qui échoue est donc retenu (`attente.json`) et relancé jusqu'à ce qu'il
réussisse, au plus `SAS_AGENT_PATIENCE` minutes : une version bloquée n'arrive jamais, on lâche.
Seul le nom déjà vérifié est relancé, jamais une nouvelle demande.
"""
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key

PREFIXE = b"sas-pme/installation/v1\n"          # le même que passerelle/installation.py
AGE_MAX = timedelta(minutes=10)
REESSAI = timedelta(seconds=float(os.environ.get("SAS_AGENT_REESSAI", "20")))
PATIENCE = timedelta(minutes=float(os.environ.get("SAS_AGENT_PATIENCE", "30")))
NOM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,213}$")
NONCE = re.compile(r"^[0-9a-f]{32}$")


def verifier(entree: dict, publique_pem: bytes, maintenant: datetime, nonces: set[str]) -> str | None:
    """Le nom à installer, ou None (avec la raison sur stderr) : rien n'est lancé sur un doute."""
    try:
        cle = load_pem_public_key(publique_pem)
        assert isinstance(cle, Ed25519PublicKey)
        texte = str(entree["demande"])
        cle.verify(base64.b64decode(entree["signature"], validate=True), PREFIXE + texte.encode())
        d = json.loads(texte)
        emis = datetime.fromisoformat(d["emis_le"].replace("Z", "+00:00"))
        if d.get("type") != "installation" or d.get("ecosysteme") != "pypi":
            raise ValueError("pas une demande d'installation pip")
        if not (isinstance(d.get("nom"), str) and NOM.match(d["nom"])):
            raise ValueError(f"nom refusé : {d.get('nom')!r}")
        if not (isinstance(d.get("nonce"), str) and NONCE.match(d["nonce"])):
            raise ValueError("nonce illisible")
        if abs(maintenant - emis) > AGE_MAX:
            raise ValueError(f"demande trop vieille ({emis.isoformat()})")
        if d["nonce"] in nonces:
            raise ValueError("demande déjà exécutée")
    except Exception as e:  # noqa: BLE001 — signature, JSON, champs : tout refus se vaut
        print(f"[sas-agent] demande n° {entree.get('n')} refusée : {type(e).__name__} {e}",
              file=sys.stderr)
        return None
    nonces.add(d["nonce"])
    return d["nom"]


def installer(nom: str, index: str, python: str | None = None) -> bool:
    """pip vers la passerelle seulement : pas d'index supplémentaire, pas de cache. L'index est en
    HTTP sur le réseau privé (comme /etc/pip.conf) : son hôte est déclaré de confiance.
    Roues seulement : une archive source exécute son setup.py à l'installation, et une demande
    signée par une plateforme prise deviendrait une exécution de code sur le serveur (C)."""
    hote = urllib.parse.urlsplit(index).hostname or ""
    r = subprocess.run([python or sys.executable, "-m", "pip", "install", "--upgrade",
                        "--no-cache-dir", "--disable-pip-version-check", "--only-binary=:all:",
                        "--index-url", index, "--trusted-host", hote, nom], check=False, timeout=600)
    return getattr(r, "returncode", 1) == 0


def _attente(etat: Path) -> dict:
    f = etat / "attente.json"
    try:
        return json.loads(f.read_text()) if f.exists() else {}
    except ValueError:
        return {}


def _retenir(etat: Path, attente: dict) -> None:
    (etat / "attente.json").write_text(json.dumps(attente, sort_keys=True))


def _attendre(etat: Path, nom: str, maintenant: datetime) -> None:
    """Retient un nom dont le pip a échoué : il sera relancé par `reessayer`."""
    attente = _attente(etat)
    jusqua = attente.get(nom, {}).get("jusqua") or (maintenant + PATIENCE).isoformat()
    attente[nom] = {"jusqua": jusqua, "prochain": (maintenant + REESSAI).isoformat()}
    _retenir(etat, attente)


def reessayer(etat: Path, executer, maintenant: datetime | None = None) -> None:
    """Relance pip pour chaque nom en attente dont l'heure est venue ; lâche après la patience."""
    maintenant = maintenant or datetime.now(timezone.utc)
    attente = _attente(etat)
    for nom, a in sorted(attente.items()):
        if maintenant > datetime.fromisoformat(a["jusqua"]):
            print(f"[sas-agent] {nom} : jamais servie après {PATIENCE}, abandon", file=sys.stderr)
            del attente[nom]
        elif maintenant >= datetime.fromisoformat(a["prochain"]):
            if executer(nom) is False:
                a["prochain"] = (maintenant + REESSAI).isoformat()
            else:
                del attente[nom]
    _retenir(etat, attente)


def tour(lire, publique_pem: bytes, etat: Path, executer, maintenant: datetime | None = None) -> None:
    """Lit les demandes après le dernier rang vu, exécute les valides, retient rang et nonces."""
    etat.mkdir(parents=True, exist_ok=True)
    f_dernier, f_nonces = etat / "dernier", etat / "nonces"
    dernier = int(f_dernier.read_text()) if f_dernier.exists() else 0
    nonces = set(f_nonces.read_text().split()) if f_nonces.exists() else set()
    maintenant = maintenant or datetime.now(timezone.utc)
    for entree in sorted(lire(dernier), key=lambda e: e.get("n", 0)):
        n = entree.get("n")
        if not isinstance(n, int) or n <= dernier:
            continue
        nom = verifier(entree, publique_pem, maintenant, nonces)
        dernier = n
        f_dernier.write_text(str(dernier))
        if nom is not None:
            with f_nonces.open("a") as f:           # retenu avant de lancer : jamais deux fois
                f.write(json.loads(entree["demande"])["nonce"] + "\n")
            if executer(nom) is False:               # pas encore servie : on réessaiera
                _attendre(etat, nom, maintenant)


def _lire_guichet(url: str):
    def lire(apres: int) -> list[dict]:
        with urllib.request.urlopen(f"{url.rstrip('/')}/v1/installations?apres={apres}",
                                    timeout=10) as r:
            return json.load(r)
    return lire


def main() -> None:
    url = os.environ.get("SAS_GUICHET_URL", "http://10.42.2.10:8444")
    index = os.environ.get("SAS_INDEX_URL", "http://10.42.2.10:8080/simple/")
    pem = Path(os.environ["SAS_CLE_PUBLIQUE"]).read_bytes()
    etat = Path(os.environ.get("SAS_AGENT_ETAT", "/var/lib/sas-agent"))
    intervalle = float(os.environ.get("SAS_AGENT_INTERVALLE", "2"))
    python = os.environ.get("SAS_AGENT_PYTHON") or sys.executable
    lire = _lire_guichet(url)
    while True:
        try:
            tour(lire, pem, etat, lambda nom: installer(nom, index, python))
            reessayer(etat, lambda nom: installer(nom, index, python))
        except Exception as e:  # noqa: BLE001 — guichet injoignable : on réessaie
            print(f"[sas-agent] {type(e).__name__} {e}", file=sys.stderr)
        time.sleep(intervalle)


if __name__ == "__main__":
    main()
