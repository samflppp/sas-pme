"""Inventaire de la passerelle : ce que les serveurs ont réellement installé.

Lu dans le journal d'accès de pypiserver (une ligne par requête HTTP). On ne retient que les
téléchargements d'archives — `GET /packages/<archive>` — car c'est le GET de l'archive qui prouve
une installation, pas la page d'index `/simple/`.

Le format de SORTIE est fixé par docs/contrats.md § 4 (`EntreeInventaire`). Le format d'ENTRÉE
(les lignes du journal) ne l'est pas : il est proposé dans docs/points/2026-10-10-C-inventaire.md.
On accepte deux formes, car la date de pypiserver vient du préambule du LogRecord
(`--log-frmt "%(asctime)s %(message)s"`), pas du message de requête :

  a) ce que pypiserver écrit réellement ici (asctime en tête, pas de code HTTP) :
       2026-10-11 09:00:01 10.42.2.20 - - "GET /packages/requests-2.32.4-...whl HTTP/1.1"
  b) le format access classique, pour un journal importé d'ailleurs :
       10.42.2.20 - - [11/Oct/2026:09:00:01 +0000] "GET /packages/...whl HTTP/1.1" 200 100

Le code HTTP est absent de la forme (a) : il n'existe pas au log de requête (`before_request`).
On ne compte donc que les GET d'archives ; quand un code est présent (forme b), on exige un 2xx.
Le parseur est tolérant : une ligne qu'il ne reconnaît pas est ignorée, jamais une exception.

`machine` (l'IP du serveur) n'est pas un champ d'`EntreeInventaire` (contrat § 1). Il est exposé
à part par `machine_par_version()` et joint au JSON brut de la route, sans toucher `commun/`
(choix option b, point C-inventaire).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from packaging.utils import (
    InvalidSdistFilename,
    InvalidWheelFilename,
    parse_sdist_filename,
    parse_wheel_filename,
)

from commun.modeles import Ecosysteme, EntreeInventaire

# Forme (a) — ce que pypiserver écrit ici : "<asctime> <IP> - - "GET /packages/<archive> HTTP/x""
# asctime par défaut de logging : "YYYY-MM-DD HH:MM:SS" ou "YYYY-MM-DD HH:MM:SS,mmm".
_FORME_A = re.compile(
    r'^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d{3})?)\s+'
    r'(?P<ip>\S+)\s+\S+\s+\S+\s+'
    r'"GET\s+/packages/(?P<archive>[^\s"?]+)[^"]*"'
)
# Forme (b) — access classique : "IP - - [date] "GET /packages/<archive> HTTP/x" <code> ..."
_FORME_B = re.compile(
    r'^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<date>[^\]]+)\]\s+'
    r'"GET\s+/packages/(?P<archive>[^\s"?]+)[^"]*"\s+(?P<code>\d{3})'
)
_FORMATS_DATE = ("%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%d %H:%M:%S", "%d/%b/%Y:%H:%M:%S %z")


def _date(brut: str) -> datetime | None:
    for fmt in _FORMATS_DATE:
        try:
            d = datetime.strptime(brut, fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


@dataclass(frozen=True)
class EntreeJournal:
    """Un téléchargement d'archive repéré dans une ligne de journal."""

    nom: str
    version: str
    ip: str
    quand: datetime


def _nom_version(archive: str) -> tuple[str, str] | None:
    """Déduit (nom normalisé, version) du nom de fichier d'archive, ou None si illisible."""
    nom_fichier = archive.rsplit("/", 1)[-1]
    try:
        if nom_fichier.endswith(".whl"):
            nom, version, *_ = parse_wheel_filename(nom_fichier)
            return nom, str(version)
        if nom_fichier.endswith((".tar.gz", ".zip")):
            nom, version = parse_sdist_filename(nom_fichier)
            return nom, str(version)
    except (InvalidWheelFilename, InvalidSdistFilename, ValueError):
        return None
    return None


def entree_journal(ligne: str) -> EntreeJournal | None:
    """Parse une ligne. None si ce n'est pas un GET d'archive (ou un code non-2xx si présent)."""
    ligne = ligne.strip()
    m = _FORME_A.match(ligne)
    if m is None:
        m = _FORME_B.match(ligne)
        if m is None:
            return None
        if not m["code"].startswith("2"):      # forme b : un code présent doit être 2xx
            return None
    nv = _nom_version(m["archive"])
    if nv is None:
        return None
    quand = _date(m["date"])
    if quand is None:
        return None
    return EntreeJournal(nom=nv[0], version=nv[1], ip=m["ip"], quand=quand)


def _entrees(lignes: Iterable[str]) -> list[EntreeJournal]:
    return [e for e in (entree_journal(l) for l in lignes) if e is not None]


def lire_journal(lignes: Iterable[str]) -> list[EntreeInventaire]:
    """Agrège les téléchargements par (nom, version) en `EntreeInventaire` (contrat § 4)."""
    compte: dict[tuple[str, str], int] = {}
    dernier: dict[tuple[str, str], datetime] = {}
    for e in _entrees(lignes):
        cle = (e.nom, e.version)
        compte[cle] = compte.get(cle, 0) + 1
        if cle not in dernier or e.quand > dernier[cle]:
            dernier[cle] = e.quand
    return [
        EntreeInventaire(
            ecosysteme=Ecosysteme.PYPI,
            nom=nom,
            version=version,
            telechargements=compte[(nom, version)],
            dernier=dernier[(nom, version)],
        )
        for (nom, version) in sorted(compte)
    ]


def machine_par_version(lignes: Iterable[str]) -> dict[tuple[str, str], list[str]]:
    """Les IP distinctes ayant téléchargé chaque (nom, version), hors contrat `EntreeInventaire`."""
    machines: dict[tuple[str, str], list[str]] = {}
    for e in _entrees(lignes):
        cle = (e.nom, e.version)
        if e.ip not in machines.setdefault(cle, []):
            machines[cle].append(e.ip)
    return machines
