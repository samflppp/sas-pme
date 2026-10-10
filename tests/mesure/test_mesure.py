"""Mesure (B) : taux de détection et de fausses alertes d'un ensemble de contrôles sur le corpus."""
import importlib.util
from pathlib import Path

from commun.modeles import Ecosysteme, Niveau, Signal, Source

RACINE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("mesurer", RACINE / "mesure" / "mesurer.py")
mesurer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mesurer)

CORPUS = {
    "malveillants": [{"ecosysteme": "pypi", "nom": f"mal{i}", "version": "1.0", "ref": f"MAL-{i}"}
                     for i in range(4)],
    "sains": [{"ecosysteme": "pypi", "nom": f"sain{i}", "version": "2.0"} for i in range(5)],
}


def detecteur(eco, nom, version):
    """Détecte mal0 et mal1 (FORT), alerte faiblement mal2 (MOYEN), fausse alerte sur sain0."""
    niveau = {"mal0": Niveau.FORT, "mal1": Niveau.BLOQUANT, "mal2": Niveau.MOYEN,
              "sain0": Niveau.FORT}.get(nom)
    return [] if niveau is None else [Signal(ecosysteme=eco, nom=nom, version=version,
                                             source=Source.STATIQUE, niveau=niveau, sorte="test")]


def test_compte_detections_et_fausses_alertes():
    r = mesurer.mesurer(CORPUS, detecteur)
    assert (r.detectes, r.malveillants, r.fausses_alertes, r.sains) == (2, 4, 1, 5)
    assert r.taux_detection == 0.5 and r.taux_fausses_alertes == 0.2
    assert r.manques == ["mal2 1.0", "mal3 1.0"]      # MOYEN ne suffit pas à arrêter une version
    assert r.alertes_a_tort == ["sain0 2.0"]


def test_le_detecteur_recoit_l_ecosysteme_type():
    vus = []
    mesurer.mesurer(CORPUS, lambda eco, nom, version: vus.append(eco) or [])
    assert set(vus) == {Ecosysteme.PYPI}


def test_tableau_markdown():
    md = mesurer.tableau({"Contrôles seuls": mesurer.mesurer(CORPUS, detecteur)})
    assert "| Contrôles seuls | 2 / 4 (50 %) | 1 / 5 (20 %) |" in md


def test_le_rapport_dit_ses_limites():
    md = mesurer.rapport(CORPUS, {"Contrôles seuls": mesurer.mesurer(CORPUS, detecteur)})
    assert "## Limites" in md and "OpenSSF" in md


def test_une_version_non_mesurable_sort_du_compte_et_est_listee():
    def detecteur_partiel(eco, nom, version):
        return None if nom in ("mal3", "sain4") else detecteur(eco, nom, version)
    r = mesurer.mesurer(CORPUS, detecteur_partiel)
    assert (r.detectes, r.malveillants, r.fausses_alertes, r.sains) == (2, 3, 1, 4)
    assert r.non_mesures == ["mal3 1.0", "sain4 2.0"]
    md = mesurer.rapport(CORPUS, {"Statique": r})
    assert "Non mesurées (2)" in md and "`sain4 2.0`" in md
