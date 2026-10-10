"""Client PyPI : lit l'API JSON publique, choisit la dernière version mûre, télécharge en vérifiant.

Ne sortent vers Internet que le nom du paquet et des téléchargements publics. La base est réglable
par SAS_PYPI_URL (source amont de démo, voir docs/architecture.md § 7).
"""
import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from packaging.version import InvalidVersion, Version as VersionPep440

BASE = os.environ.get("SAS_PYPI_URL", "https://pypi.org")
DELAI = timedelta(days=3)


def metadonnees(nom: str, *, client: httpx.Client, base: str = BASE) -> dict:
    r = client.get(f"{base}/pypi/{nom}/json")
    if r.status_code == 404:
        raise LookupError(f"paquet inconnu sur PyPI : {nom}")
    r.raise_for_status()
    return r.json()


def _date(fichiers: list[dict]) -> datetime:
    return min(datetime.fromisoformat(f["upload_time_iso_8601"].replace("Z", "+00:00"))
               for f in fichiers)


def versions_publiees(nom: str, *, client: httpx.Client, base: str = BASE
                      ) -> list[tuple[str, datetime]]:
    """Versions stables, non retirées, avec au moins un fichier ; triées de la plus ancienne."""
    retenues = []
    for version, fichiers in metadonnees(nom, client=client, base=base)["releases"].items():
        try:
            pep = VersionPep440(version)
        except InvalidVersion:
            continue
        if pep.is_prerelease or not fichiers or any(f.get("yanked") for f in fichiers):
            continue
        retenues.append((pep, version, _date(fichiers)))
    return [(v, d) for _, v, d in sorted(retenues)]


def derniere_version_mure(nom: str, maintenant: datetime, *, delai: timedelta = DELAI,
                          client: httpx.Client, base: str = BASE) -> tuple[str, datetime] | None:
    """La plus haute version publiée depuis au moins `delai`, ou None."""
    mures = [(v, d) for v, d in versions_publiees(nom, client=client, base=base)
             if maintenant - d >= delai]
    return mures[-1] if mures else None


def telecharger(nom: str, version: str, dossier: Path, *, client: httpx.Client,
                base: str = BASE) -> list[Path]:
    """Télécharge tous les fichiers d'une version et vérifie chaque sha256 annoncé par PyPI."""
    fichiers = metadonnees(nom, client=client, base=base)["releases"].get(version) or []
    if not fichiers:
        raise LookupError(f"aucun fichier pour {nom} {version}")
    for f in fichiers:
        if Path(f["filename"]).name != f["filename"] or f["filename"].startswith("."):
            raise ValueError(f"nom de fichier refusé : {f['filename']!r}")
    dossier.mkdir(parents=True, exist_ok=True)
    ecrits: list[Path] = []
    try:
        for f in fichiers:
            r = client.get(f["url"])
            r.raise_for_status()
            if hashlib.sha256(r.content).hexdigest() != f["digests"]["sha256"]:
                raise ValueError(f"sha256 différent pour {f['filename']}")
            chemin = dossier / f["filename"]
            chemin.write_bytes(r.content)
            ecrits.append(chemin)
    except Exception:
        for chemin in ecrits:
            chemin.unlink(missing_ok=True)
        raise
    return ecrits
