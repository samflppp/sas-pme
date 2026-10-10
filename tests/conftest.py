"""Fixtures partagées. Chacun ajoute les siennes dans son bloc."""

# --- A (Sam) ---
import pytest


@pytest.fixture(autouse=True)
def _cle_journal(monkeypatch):
    """La base refuse de démarrer sans SAS_CLE_JOURNAL (clé HMAC du journal, hors de la base)."""
    monkeypatch.setenv("SAS_CLE_JOURNAL", "cle-de-journal-des-tests-pas-un-secret")

# --- B (Mouabd19) ---

# --- C (STEUSSO) ---
