"""Client PyPI : lit l'API JSON publique, choisit la dernière version mûre, télécharge en vérifiant.

Ne sortent vers Internet que le nom du paquet et des téléchargements publics. La base est réglable
par SAS_PYPI_URL (source amont de démo, voir docs/architecture.md § 7), le délai par SAS_DELAI.
"""
import hashlib
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from packaging.markers import default_environment
from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import compatible_tags, cpython_tags
from packaging.utils import InvalidWheelFilename, parse_wheel_filename
from packaging.version import InvalidVersion, Version as VersionPep440

BASE = os.environ.get("SAS_PYPI_URL", "https://pypi.org")
DELAI = timedelta(days=3)
# Nom de projet PEP 508 : rien qui puisse sortir du chemin /pypi/<nom>/json.
# Environnement des serveurs sensibles : sert à garder les seules dépendances qui s'y installent.
CIBLE = {**default_environment(), "python_version": "3.12", "python_full_version": "3.12.0",
         "implementation_name": "cpython", "platform_python_implementation": "CPython",
         "sys_platform": "linux", "platform_system": "Linux", "os_name": "posix",
         "platform_machine": "x86_64", "extra": ""}
# Roues installables sur les serveurs (Ubuntu 24.04 : CPython 3.12, x86_64, glibc 2.39).
_PLATEFORMES = [*(f"manylinux_2_{x}_x86_64" for x in range(39, 4, -1)), "manylinux2014_x86_64",
                "manylinux2010_x86_64", "manylinux1_x86_64", "linux_x86_64"]
_TAGS_CIBLE = {*cpython_tags((3, 12), abis=["cp312"], platforms=_PLATEFORMES),
               *compatible_tags((3, 12), "cp312", _PLATEFORMES)}
_NOM_VALIDE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]{0,212}[A-Za-z0-9])?$")


def delai() -> timedelta:
    """Délai d'attente : SAS_DELAI en secondes entières (démo : 120), sinon 3 jours.

    Lu à chaque appel. Une valeur illisible ou nulle est refusée : elle ne doit jamais annuler
    l'attente en silence.
    """
    brut = os.environ.get("SAS_DELAI", "").strip()
    if not brut:
        return DELAI
    if not brut.isdigit() or int(brut) == 0:
        raise ValueError(f"SAS_DELAI doit être un nombre entier de secondes > 0, pas {brut!r}")
    return timedelta(seconds=int(brut))


def texte_delai(d: timedelta) -> str:
    return f"{d.days} jours" if d == timedelta(days=d.days) else f"{int(d.total_seconds())} s"


def metadonnees(nom: str, *, client: httpx.Client, base: str = BASE) -> dict:
    if not _NOM_VALIDE.match(nom):
        raise ValueError(f"nom de paquet invalide : {nom!r}")
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
                          specifier: SpecifierSet | None = None, client: httpx.Client,
                          base: str = BASE) -> tuple[str, datetime] | None:
    """La plus haute version publiée depuis au moins `delai` (et dans `specifier`), ou None."""
    mures = [(v, d) for v, d in versions_publiees(nom, client=client, base=base)
             if maintenant - d >= delai and (specifier is None or specifier.contains(v))]
    return mures[-1] if mures else None


def dependances(nom: str, version: str, *, client: httpx.Client, base: str = BASE
                 ) -> list[Requirement]:
    """Dépendances obligatoires d'une version sur les serveurs (ni extras, ni autres plateformes)."""
    if not _NOM_VALIDE.match(nom):
        raise ValueError(f"nom de paquet invalide : {nom!r}")
    r = client.get(f"{base}/pypi/{nom}/{version}/json")
    r.raise_for_status()
    gardees = []
    for brute in r.json()["info"].get("requires_dist") or []:
        try:
            req = Requirement(brute)
        except InvalidRequirement:
            raise ValueError(f"dépendance illisible pour {nom} {version} : {brute!r}") from None
        if req.marker is None or req.marker.evaluate(CIBLE):
            gardees.append(req)
    return gardees


def _pour_la_cible(nom_fichier: str) -> bool:
    if nom_fichier.endswith(".whl"):
        try:
            return not parse_wheel_filename(nom_fichier)[3].isdisjoint(_TAGS_CIBLE)
        except InvalidWheelFilename:
            return False
    return nom_fichier.endswith((".tar.gz", ".zip"))  # source : le code d'installation y est


def pour_la_cible(fichiers: list[dict]) -> list[dict]:
    """Les roues que les serveurs installent, plus la source ; ni Windows, ni macOS, ni wasm…"""
    return [f for f in fichiers if _pour_la_cible(f["filename"])]


def telecharger(nom: str, version: str, dossier: Path, *, client: httpx.Client,
                base: str = BASE) -> list[Path]:
    """Télécharge les fichiers d'une version utiles aux serveurs et vérifie chaque sha256."""
    fichiers = metadonnees(nom, client=client, base=base)["releases"].get(version) or []
    if not fichiers:
        raise LookupError(f"aucun fichier pour {nom} {version}")
    for f in fichiers:
        if not f["filename"] or Path(f["filename"]).name != f["filename"] \
                or f["filename"].startswith("."):
            raise ValueError(f"nom de fichier refusé : {f['filename']!r}")
    fichiers = pour_la_cible(fichiers)
    if not fichiers:
        raise LookupError(f"{nom} {version} : aucun fichier pour la cible (Linux x86_64, "
                          "CPython 3.12)")
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
