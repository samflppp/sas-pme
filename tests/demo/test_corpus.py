"""Tests du corpus de mesure (B) : demo/corpus/."""

import importlib.util
import json
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
CORPUS = RACINE / "demo" / "corpus" / "corpus.json"


def _charger_construire():
    chemin = RACINE / "demo" / "corpus" / "construire.py"
    spec = importlib.util.spec_from_file_location("construire", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


construire = _charger_construire()


def _osv(id_="MAL-2025-1", nom="reqeusts", versions=("1.0.0",), details=None):
    affected = {"package": {"ecosystem": "PyPI", "name": nom}}
    if versions:
        affected["versions"] = list(versions)
    else:
        affected["ranges"] = [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}]}]
    return {
        "id": id_,
        "published": "2025-03-01T10:00:00Z",
        "summary": f"Malicious code in {nom} (PyPI)",
        "details": details
        or "\n## Source: kam193\nSteals credentials.\n\nCategory: MALICIOUS - x\n\nCampaign: c1\n",
        "affected": [affected],
        "database_specific": {"iocs": {"urls": ["http://evil.example:8080/x"]}},
    }


# --- extraction d'un rapport OSV -------------------------------------------------


def test_extraire_rapport_avec_version_exacte():
    e = construire.extraire_malveillant(_osv())
    assert e["nom"] == "reqeusts"
    assert e["version"] == "1.0.0"
    assert e["ref"] == "MAL-2025-1"
    assert e["campagne"] == "c1"
    assert e["domaines_ioc"] == ["evil.example"]


def test_rapport_sans_version_exacte_ignore():
    assert construire.extraire_malveillant(_osv(versions=())) is None


def test_rapport_non_malveillant_ignore():
    osv = _osv(details="Category: SECURITY_HOLDING - placeholder")
    assert construire.extraire_malveillant(osv) is None


def test_choix_malveillants_unique_et_plafond_par_campagne():
    rapports = [_osv(id_=f"MAL-2025-{i}", nom=f"p{i}") for i in range(10)]
    choix = construire.choisir_malveillants(rapports, n=5, par_campagne=2)
    assert len(choix) == 2  # une seule campagne "c1", plafonnée à 2


# --- choix d'une mise à jour saine ------------------------------------------------


def _pypi(releases):
    return {"info": {"name": "requests"}, "releases": releases}


def _fichier(date, yanked=False):
    return [{"upload_time_iso_8601": date, "yanked": yanked, "packagetype": "bdist_wheel"}]


def test_choisir_sain_prend_les_deux_dernieres_stables():
    data = _pypi(
        {
            "2.31.0": _fichier("2023-05-22T00:00:00Z"),
            "2.32.3": _fichier("2024-05-29T00:00:00Z"),
            "2.32.4": _fichier("2025-06-09T00:00:00Z"),
            "2.33.0rc1": _fichier("2025-07-01T00:00:00Z"),
            "2.32.5": _fichier("2025-08-01T00:00:00Z", yanked=True),
        }
    )
    e = construire.choisir_sain("requests", data)
    assert (e["version_precedente"], e["version"]) == ("2.32.3", "2.32.4")
    assert e["publiee_le"] == "2025-06-09T00:00:00Z"


def test_choisir_sain_ignore_les_versions_trop_recentes():
    from datetime import datetime, timezone

    data = _pypi(
        {
            "1.0": _fichier("2024-01-01T00:00:00Z"),
            "1.1": _fichier("2024-06-01T00:00:00Z"),
            "1.2": _fichier("2025-01-10T00:00:00Z"),
        }
    )
    limite = datetime(2025, 1, 1, tzinfo=timezone.utc)
    e = construire.choisir_sain("x", data, limite=limite)
    assert (e["version_precedente"], e["version"]) == ("1.0", "1.1")


def test_choisir_sain_sans_assez_de_versions():
    assert construire.choisir_sain("x", _pypi({"1.0": _fichier("2024-01-01T00:00:00Z")})) is None


# --- le corpus figé ---------------------------------------------------------------


@pytest.fixture(scope="module")
def corpus():
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def test_corpus_compte(corpus):
    assert len(corpus["malveillants"]) == 30
    assert len(corpus["sains"]) == 50


def test_corpus_malveillants_bien_formes(corpus):
    noms = set()
    for e in corpus["malveillants"]:
        assert e["ecosysteme"] == "pypi"
        assert e["ref"].startswith("MAL-")
        assert e["nom"] and e["version"]
        noms.add(e["nom"])
    assert len(noms) == 30


def test_corpus_sains_bien_formes(corpus):
    noms = {e["nom"] for e in corpus["sains"]}
    assert len(noms) == 50
    for e in corpus["sains"]:
        assert e["ecosysteme"] == "pypi"
        assert e["version"] != e["version_precedente"]


def test_corpus_aucun_paquet_dans_les_deux_listes(corpus):
    mal = {e["nom"].lower() for e in corpus["malveillants"]}
    sain = {e["nom"].lower() for e in corpus["sains"]}
    assert not mal & sain
