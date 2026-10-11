"""Client npm : lit le registre public, choisit la dernière version mûre, télécharge en vérifiant.

Le pendant de `pypi.py` pour npm. Ne sortent vers Internet que le nom du paquet et des
téléchargements publics. La base est réglable par SAS_NPM_URL (source amont de démo), le délai est
celui de `pypi.delai()` (SAS_DELAI), commun aux deux écosystèmes.

- Une version retenue est stable (pas de préversion), non dépréciée, avec une archive.
- L'archive (`.tgz`) est vérifiée par son intégrité `sha512` (à défaut, le `sha1` historique).
"""
import base64
import hashlib
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import httpx

from plateforme.pipeline import semver

BASE = os.environ.get("SAS_NPM_URL", "https://registry.npmjs.org")
DELAI = timedelta(days=3)
# Nom npm : minuscules, éventuellement à portée (@org/nom) ; rien qui sorte du chemin de l'URL.
_NOM_VALIDE = re.compile(r"^(@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]{0,213}$")
_FICHIER_VALIDE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._~-]*\.tgz$")


def valider(nom: str) -> str:
    if not _NOM_VALIDE.match(nom) or ".." in nom:
        raise ValueError(f"nom de paquet npm invalide : {nom!r}")
    return nom


def _url(nom: str, base: str) -> str:
    return f"{base}/{quote(valider(nom), safe='@')}"


def metadonnees(nom: str, *, client: httpx.Client, base: str = BASE) -> dict:
    r = client.get(_url(nom, base))
    if r.status_code == 404:
        raise LookupError(f"paquet inconnu sur npm : {nom}")
    r.raise_for_status()
    return r.json()


def _date(texte: str) -> datetime:
    return datetime.fromisoformat(texte.replace("Z", "+00:00"))


def versions_publiees(nom: str, *, client: httpx.Client, base: str = BASE
                      ) -> list[tuple[str, datetime]]:
    """Versions stables, non dépréciées, avec une archive ; triées de la plus ancienne."""
    m = metadonnees(nom, client=client, base=base)
    dates = m.get("time") or {}
    retenues = []
    for version, info in (m.get("versions") or {}).items():
        if (semver.lire(version) is None or semver.preversion(version) or info.get("deprecated")
                or not (info.get("dist") or {}).get("tarball") or version not in dates):
            continue
        retenues.append((semver.cle(version), version, _date(dates[version])))
    return [(v, d) for _, v, d in sorted(retenues)]


def derniere_version_mure(nom: str, maintenant: datetime, *, delai: timedelta = DELAI,
                          plage: str | None = None, client: httpx.Client, base: str = BASE
                          ) -> tuple[str, datetime] | None:
    """La plus haute version publiée depuis au moins `delai` (et dans `plage`), ou None."""
    p = semver.Plage(plage) if plage else None
    mures = [(v, d) for v, d in versions_publiees(nom, client=client, base=base)
             if maintenant - d >= delai and (p is None or p.contient(v))]
    return mures[-1] if mures else None


def dependances(nom: str, version: str, *, client: httpx.Client, base: str = BASE
                ) -> dict[str, str]:
    """Dépendances obligatoires d'une version : {nom : plage}. Les dépendances optionnelles, de
    développement et « peer » ne sont pas installées sur les serveurs par ce chemin."""
    info = (metadonnees(nom, client=client, base=base).get("versions") or {}).get(version)
    if info is None:
        raise LookupError(f"{nom} {version} : version inconnue sur npm")
    return dict(info.get("dependencies") or {})


def _verifier(octets: bytes, dist: dict, fichier: str) -> None:
    integrite = dist.get("integrity") or ""
    if integrite.startswith("sha512-"):
        attendu = integrite.removeprefix("sha512-")
        if base64.b64encode(hashlib.sha512(octets).digest()).decode() != attendu:
            raise ValueError(f"intégrité sha512 différente pour {fichier}")
    elif dist.get("shasum"):
        if hashlib.sha1(octets).hexdigest() != dist["shasum"]:
            raise ValueError(f"intégrité sha1 différente pour {fichier}")
    else:
        raise ValueError(f"{fichier} : ni sha512 ni sha1 publiés, archive invérifiable")


def telecharger(nom: str, version: str, dossier: Path, *, client: httpx.Client,
                base: str = BASE) -> list[Path]:
    """Télécharge l'archive `.tgz` d'une version et vérifie son intégrité."""
    info = (metadonnees(nom, client=client, base=base).get("versions") or {}).get(version)
    if info is None:
        raise LookupError(f"aucune archive pour {nom} {version}")
    dist = info.get("dist") or {}
    url = dist.get("tarball") or ""
    fichier = unquote(urlsplit(url).path.rsplit("/", 1)[-1])
    if not _FICHIER_VALIDE.match(fichier) or ".." in fichier:
        raise ValueError(f"nom d'archive refusé : {fichier!r}")
    r = client.get(url)
    r.raise_for_status()
    _verifier(r.content, dist, fichier)
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / fichier
    chemin.write_bytes(r.content)
    return [chemin]
