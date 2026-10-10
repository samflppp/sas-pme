"""Copie provisoire des types de docs/contrats.md § 1, tant que commun/modeles.py (A, M0) n'existe pas.

À supprimer dès que commun/ est dans main : __init__.py importe alors commun.modeles.
"""

from enum import StrEnum

from pydantic import BaseModel


class Ecosysteme(StrEnum):
    PYPI = "pypi"
    NPM = "npm"


class RapportSandbox(BaseModel):
    requetes_dns: list[str]
    connexions: list[str]  # "hote:port"
    fichiers_sensibles: list[str]
    leurres_lus: list[str]
    processus: list[str]
    code_sortie: int
    duree_s: float
    delai_depasse: bool
