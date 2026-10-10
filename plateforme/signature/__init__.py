"""Signature et publication vers la passerelle (C). Stub M0 (docs/contrats.md § 4).

M0 : aucune signature, les archives sont copiées par scp dans le dossier de pypiserver.
M1 : manifeste signé Ed25519 + POST /v1/publish en TLS mutuel ; mêmes signatures de fonctions.

Configuration (variables d'environnement, jamais dans Git) :
  SAS_PASSERELLE_SSH    utilisateur@ip de la passerelle, ex. ubuntu@10.42.2.10
  SAS_PASSERELLE_DEPOT  dossier servi par pypiserver (défaut /srv/pypi/packages)
  SAS_PASSERELLE_CLE    clé SSH privée de la plateforme (facultatif)
"""

import os
import re
import subprocess
from pathlib import Path

__all__ = ["publier", "revoquer", "lire_inventaire"]

_NOM_SUR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _config() -> tuple[str, str, list[str]]:
    hote = os.environ["SAS_PASSERELLE_SSH"]
    depot = os.environ.get("SAS_PASSERELLE_DEPOT", "/srv/pypi/packages").rstrip("/")
    cle = os.environ.get("SAS_PASSERELLE_CLE")
    options = ["-o", "BatchMode=yes"] + (["-i", cle] if cle else [])
    return hote, depot, options


def _verifier_pypi(ecosysteme) -> None:
    if str(ecosysteme) != "pypi":
        raise NotImplementedError("M0 : pip seulement")


def publier(ecosysteme, nom: str, version: str, archives: list[Path], verdict_id: int) -> None:
    _verifier_pypi(ecosysteme)
    if not archives:
        raise ValueError("aucune archive à publier")
    for a in archives:
        if not Path(a).is_file():
            raise FileNotFoundError(a)
    hote, depot, options = _config()
    subprocess.run(
        ["scp", *options, *map(str, archives), f"{hote}:{depot}/"], check=True, timeout=120
    )


def revoquer(ecosysteme, nom: str, version: str, raison: str) -> None:
    _verifier_pypi(ecosysteme)
    if not (_NOM_SUR.match(nom) and _NOM_SUR.match(version)) or ".." in nom + version:
        raise ValueError(f"nom ou version refusé : {nom!r} {version!r}")
    hote, depot, options = _config()
    # Les wheels remplacent « - » par « _ » dans le nom ; les sdist gardent souvent le nom tel quel.
    noms = dict.fromkeys([nom, nom.replace("-", "_")])
    motifs = " ".join(f"{depot}/{n}-{version}[.-]*" for n in noms)
    subprocess.run(["ssh", *options, hote, f"rm -f -- {motifs}"], check=True, timeout=60)


def lire_inventaire() -> list:
    return []  # M1 : GET /v1/inventory sur la passerelle
