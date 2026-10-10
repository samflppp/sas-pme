"""Contrats partagés par les trois pistes (tâche 0).

Ce fichier ne change qu'aux points de synchronisation, sur `main`.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class State(StrEnum):
    """État d'une version. `permissiveness` ordonne du plus strict au plus permissif."""

    QUARANTINE = "quarantine"
    APPROVED = "approved"
    FAST_TRACK = "fast_track"
    REVIEW = "review"
    BLOCKED = "blocked"

    @property
    def permissiveness(self) -> int:
        return _PERMISSIVENESS[self]


_PERMISSIVENESS = {
    State.BLOCKED: 0,
    State.REVIEW: 1,
    State.QUARANTINE: 2,
    State.FAST_TRACK: 3,
    State.APPROVED: 4,
}


class Level(StrEnum):
    """Gravité d'un signal. `rank` ordonne du plus faible au plus grave."""

    INFO = "info"
    MEDIUM = "medium"
    STRONG = "strong"
    BLOCK = "block"

    @property
    def rank(self) -> int:
        return _RANK[self]


_RANK = {Level.INFO: 0, Level.MEDIUM: 1, Level.STRONG: 2, Level.BLOCK: 3}


class Source(StrEnum):
    CHECKS = "checks"
    DIFF = "diff"
    LLM = "llm"
    WATCH = "watch"
    EGRESS = "egress"


@dataclass(frozen=True)
class Signal:
    """Un indice levé sur une version (ou sur un poste quand `name` est vide)."""

    name: str  # nom normalisé PEP 503
    version: str
    source: Source
    level: Level
    kind: str  # ex. "typosquat", "exec_in_setup", "osv", "correlation"
    # {"file":..,"line":..,"excerpt":..,"url":..} ; hors égalité et hors hash
    evidence: dict = field(default_factory=dict, compare=False, hash=False)
    structured: bool = True  # False pour un article de source libre
    certainty: str = ""  # "haute" | "moyenne" | "basse" pour la source llm


@dataclass(frozen=True)
class Finding:
    """Constat de l'étage 2 (diff entre versions)."""

    kind: str
    file: str
    line: int
    excerpt: str  # 200 caractères au plus


@dataclass(frozen=True)
class Flow:
    """Une connexion sortante relayée par le proxy, sans son contenu."""

    host: str  # IP source du poste
    domain: str
    port: int
    started_at: datetime
    bytes_up: int
    bytes_down: int
    duration_ms: int


@dataclass(frozen=True)
class HumanDecision:
    state: State
    actor: str
    reason: str
    at: datetime
