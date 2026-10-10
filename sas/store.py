"""Accès SQLite (tâche A1, Sam).

T0 ne fixe que les signatures : B et C codent contre elles dès maintenant.
Les corps sont écrits en A1 ; jusque-là, tout appel lève NotImplementedError.
"""
from datetime import datetime

from sas.models import Flow, HumanDecision, Signal, State


class Store:
    def __init__(self, path: str):
        self.path = path

    # --- versions -----------------------------------------------------------
    def upsert_version(self, name: str, version: str, published_at: datetime,
                       discovered_at: datetime) -> bool:
        """True si la version est nouvelle."""
        raise NotImplementedError("A1")

    def set_state(self, name: str, version: str, state: State, reason: str) -> None:
        raise NotImplementedError("A1")

    def get_state(self, name: str, version: str) -> State | None:
        raise NotImplementedError("A1")

    def visible_versions(self, name: str) -> set[str]:
        """Versions à l'état approved ou fast_track."""
        raise NotImplementedError("A1")

    # --- signaux et décisions ----------------------------------------------
    def add_signal(self, s: Signal) -> int:
        raise NotImplementedError("A1")

    def signals_for(self, name: str, version: str) -> list[Signal]:
        raise NotImplementedError("A1")

    def add_decision(self, name: str, version: str, d: HumanDecision) -> None:
        raise NotImplementedError("A1")

    def decision_for(self, name: str, version: str) -> HumanDecision | None:
        raise NotImplementedError("A1")

    # --- installations ------------------------------------------------------
    def record_install(self, host: str, name: str, version: str, at: datetime) -> None:
        raise NotImplementedError("A1")

    def installs_by_host(self, host: str, since: datetime) -> list[tuple[str, str, datetime]]:
        """(nom, version, heure) installés par ce poste depuis `since`."""
        raise NotImplementedError("A1")

    def hosts_with(self, name: str, version: str) -> list[str]:
        raise NotImplementedError("A1")

    # --- sorties (utilisé par C) -------------------------------------------
    def add_flow(self, f: Flow) -> None:
        raise NotImplementedError("A1")

    def flows(self, host: str | None = None, domain: str | None = None) -> list[Flow]:
        raise NotImplementedError("A1")

    def domain_first_seen(self, domain: str) -> datetime | None:
        raise NotImplementedError("A1")

    def block_domain(self, domain: str, reason: str) -> None:
        raise NotImplementedError("A1")

    def is_domain_blocked(self, domain: str) -> bool:
        raise NotImplementedError("A1")

    def host_kind(self, host: str) -> str:
        """'dev' par défaut, 'ci' si déclaré."""
        raise NotImplementedError("A1")

    def ci_allowed(self, host: str, domain: str) -> bool:
        raise NotImplementedError("A1")

    def add_alert(self, host: str, summary_fr: str, signal_ids: list[int]) -> int:
        raise NotImplementedError("A1")
