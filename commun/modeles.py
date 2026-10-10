"""Contrats partagés (docs/contrats.md). Un changement ici = une PR relue par A, B et C.

Deux règles du produit sont tenues ici, au niveau des types, pour qu'aucun code ne puisse les
contourner :
- un signal du LLM ne peut pas être bloquant (le LLM alerte, il ne décide pas) ;
- un article de source libre ne peut pas être bloquant (il met « à revoir », jamais plus).
"""
import json
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Ecosysteme(StrEnum):
    PYPI = "pypi"
    NPM = "npm"


class Etat(StrEnum):
    NOUVELLE = "nouvelle"
    EN_ATTENTE = "en_attente"      # délai de 3 jours, veille active
    EN_ANALYSE = "en_analyse"
    A_REVOIR = "a_revoir"
    APPROUVEE = "approuvee"
    BLOQUEE = "bloquee"
    PUBLIEE = "publiee"            # présente dans la passerelle
    REVOQUEE = "revoquee"          # retirée de la passerelle après coup


class Niveau(StrEnum):
    INFO = "info"
    MOYEN = "moyen"
    FORT = "fort"
    BLOQUANT = "bloquant"

    @property
    def rang(self) -> int:
        return _RANG[self]


_RANG = {Niveau.INFO: 0, Niveau.MOYEN: 1, Niveau.FORT: 2, Niveau.BLOQUANT: 3}


class Source(StrEnum):
    STATIQUE = "statique"
    SANDBOX = "sandbox"
    LLM = "llm"
    VEILLE = "veille"
    HUMAIN = "humain"


class _Modele(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Version(_Modele):
    ecosysteme: Ecosysteme
    nom: str
    version: str
    publiee_le: datetime   # date de publication sur PyPI ou npm
    detectee_le: datetime
    etat: Etat


class Signal(_Modele):
    ecosysteme: Ecosysteme
    nom: str
    version: str
    source: Source
    niveau: Niveau
    sorte: str               # ex. "typosquat", "dns_exfil", "lit_leurre", "article"
    preuve: dict = Field(default_factory=dict)  # {"fichier","ligne","extrait","url","ref_rag"}
    structure: bool = True   # False pour un article de source libre

    @model_validator(mode="after")
    def _ni_llm_ni_article_ne_bloquent(self) -> "Signal":
        if self.niveau is Niveau.BLOQUANT and self.source is Source.LLM:
            raise ValueError("un signal du LLM est au plus FORT : le LLM alerte, il ne décide pas")
        if self.niveau is Niveau.BLOQUANT and self.source is Source.VEILLE and not self.structure:
            raise ValueError("un article de source libre est au plus FORT : il met « à revoir »")
        return self


class RapportSandbox(_Modele):
    requetes_dns: list[str]
    connexions: list[str]          # "hote:port"
    fichiers_sensibles: list[str]
    leurres_lus: list[str]
    processus: list[str]
    code_sortie: int
    duree_s: float
    delai_depasse: bool


class Verdict(_Modele):
    etat: Literal[Etat.APPROUVEE, Etat.A_REVOIR, Etat.BLOQUEE]
    raison: str                    # une phrase en français
    signaux: list[Signal]
    explication_llm: str = ""
    refs_rag: list[str] = Field(default_factory=list)


class EntreeInventaire(_Modele):
    ecosysteme: Ecosysteme
    nom: str
    version: str
    telechargements: int
    dernier: datetime | None


class FichierManifeste(_Modele):
    nom: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Manifeste(_Modele):
    """Ce que la plateforme signe et que la passerelle vérifie (docs/contrats.md § 4)."""

    type: Literal["publication", "revocation"]
    ecosysteme: Ecosysteme
    nom: str
    version: str
    fichiers: list[FichierManifeste] = Field(default_factory=list)  # vide pour une révocation
    verdict_id: int | None = None
    approuve_le: datetime | None = None
    emis_le: datetime
    nonce: str
    raison: str = ""               # pour une révocation


def canonique(m: Manifeste) -> bytes:
    """Octets exacts à signer : JSON, clés triées, sans espaces, UTF-8."""
    return json.dumps(m.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
