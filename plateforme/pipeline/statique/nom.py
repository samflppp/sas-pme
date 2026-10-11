"""Contrôle sur le nom : typosquat d'un paquet populaire (« reqeusts » pour « requests »).

Le nom seul suffit : ce contrôle marche même sur un paquet déjà retiré de PyPI. Chaque écosystème a
sa liste de paquets populaires (PyPI : hugovk/top-pypi-packages ; npm : npm-high-impact).
"""
from functools import cache
from pathlib import Path

from packaging.utils import canonicalize_name
from rapidfuzz import process
from rapidfuzz.distance import Levenshtein

from commun.modeles import Ecosysteme, Niveau, Signal, Source

_DONNEES = Path(__file__).resolve().parents[1] / "donnees"
_LISTES = {Ecosysteme.PYPI: _DONNEES / "populaires_pypi.txt",
           Ecosysteme.NPM: _DONNEES / "populaires_npm.txt"}
LONGUEUR_MIN = 5  # en dessous, une ou deux lettres d'écart touchent trop de noms légitimes


@cache
def populaires(eco: Ecosysteme = Ecosysteme.PYPI) -> frozenset[str]:
    lignes = _LISTES[eco].read_text(encoding="utf-8").splitlines()
    return frozenset(l for l in lignes if l and not l.startswith("#"))


def typosquat(nom: str, populaires_: set[str] | frozenset[str],
              eco: Ecosysteme = Ecosysteme.PYPI) -> str | None:
    """Le paquet populaire que `nom` imite à une ou deux lettres près, ou None."""
    canon = nom.lower() if eco is Ecosysteme.NPM else canonicalize_name(nom)
    if canon in populaires_ or len(canon) < LONGUEUR_MIN:
        return None
    ecart_max = 1 if len(canon) < 8 else 2
    trouve = process.extractOne(canon, populaires_, scorer=Levenshtein.distance,
                                score_cutoff=ecart_max)
    return trouve[0] if trouve else None


def controler_nom(eco: Ecosysteme, nom: str, version: str,
                  populaires_: set[str] | frozenset[str] | None = None) -> list[Signal]:
    cible = typosquat(nom, populaires(eco) if populaires_ is None else populaires_, eco)
    if cible is None:
        return []
    return [Signal(ecosysteme=eco, nom=nom, version=version, source=Source.STATIQUE,
                   niveau=Niveau.FORT, sorte="typosquat",
                   preuve={"cible": cible, "extrait": f"« {nom} » imite le paquet populaire « {cible} »"})]
