"""Réglages, lus depuis l'environnement (préfixe `SAS_`). Une ligne par réglage ; chacun ajoute en bas."""
import os
from dataclasses import dataclass
from datetime import timedelta


def _env(name: str, default: str) -> str:
    return os.environ.get(f"SAS_{name}", default)


@dataclass(frozen=True)
class Config:
    # Commun
    db_path: str = _env("DB_PATH", "sas.db")
    cache_dir: str = _env("CACHE_DIR", "cache")
    demo_mode: bool = _env("DEMO_MODE", "0") == "1"

    # A — index et quarantaine
    upstream_url: str = _env("UPSTREAM_URL", "https://pypi.org")
    index_host: str = _env("INDEX_HOST", "0.0.0.0")
    index_port: int = int(_env("INDEX_PORT", "8080"))
    quarantine_delay: timedelta = timedelta(hours=float(_env("QUARANTINE_HOURS", "48")))
    tick_seconds: int = int(_env("TICK_SECONDS", "60"))

    # B — analyse, LLM, veille
    ollama_url: str = _env("OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model: str = _env("OLLAMA_MODEL", "qwen2.5-coder:7b")
    llm_timeout_s: float = float(_env("LLM_TIMEOUT_S", "60"))
    watch_every: timedelta = timedelta(hours=float(_env("WATCH_HOURS", "2")))
    rss_feeds: tuple[str, ...] = tuple(f for f in _env("RSS_FEEDS", "").split(",") if f)
    osv_url: str = _env("OSV_URL", "https://api.osv.dev")
    excerpt_max: int = 200

    # C — proxy et sorties
    proxy_host: str = _env("PROXY_HOST", "0.0.0.0")
    proxy_port: int = int(_env("PROXY_PORT", "3128"))
    rdap_url: str = _env("RDAP_URL", "https://rdap.org")
    correlation_window: timedelta = timedelta(minutes=10)
    young_domain: timedelta = timedelta(days=30)
    beacon_min_flows: int = 5
    beacon_max_cv: float = 0.10  # écart-type / moyenne des intervalles
    egress_agent_every: timedelta = timedelta(minutes=1 if demo_mode else 15)
