"""Vitrine pipelad.tech, version finale : aucune trace de développement, chiffres de la mesure finale."""
from pathlib import Path

VITRINE = (Path(__file__).resolve().parents[2] / "infra" / "domaine" / "vitrine" / "index.html").read_text()


def test_la_vitrine_ne_parle_ni_de_demo_ni_de_hackathon_ni_de_travail_en_cours():
    for mot in ("Ouvrir la démo", "hackathon", "en cours", "infrastructure de démo"):
        assert mot not in VITRINE, mot


def test_la_vitrine_donne_la_mesure_finale():
    assert "103 sur 128" in VITRINE and "80 %" in VITRINE
    assert "pip, npm" in VITRINE
