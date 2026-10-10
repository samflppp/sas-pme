"""pipeline.demander (B, M0) : choisit la dernière version mûre et l'enregistre en attente."""
from datetime import datetime, timedelta, timezone

import pytest
from packaging.requirements import Requirement
from packaging.version import Version
from fastapi.testclient import TestClient

from commun.modeles import Ecosysteme, Etat
from plateforme import pipeline
from plateforme.db.acces import Base
from plateforme.web.app import creer_app

MAINTENANT = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
PUBLIEE = MAINTENANT - timedelta(days=5)


# Faux index PyPI : {nom: {version: [dépendances]}}, toutes publiées il y a 5 jours.
INDEX = {
    "demo": {"1.1": []},
    "typing-extensions": {"4.12": []},
    "requests": {"2.34": ["urllib3<3,>=1.26", "idna>=2"]},
    "urllib3": {"2.5": [], "3.0": []},          # 3.0 existe mais requests veut < 3
    "idna": {"3.10": []},
    "cycle-a": {"1.0": ["cycle-b"]},
    "cycle-b": {"1.0": ["Cycle_A"]},            # retour vers cycle-a, autre graphie
    "casse": {"1.0": ["demo", "absent"]},       # « absent » n'existe pas
}


@pytest.fixture(autouse=True)
def faux_pypi(monkeypatch):
    def faux_choix(nom, maintenant, *, specifier=None, **_):
        versions = [v for v in INDEX.get(nom, {}) if specifier is None or specifier.contains(v)]
        return (max(versions, key=Version), PUBLIEE) if versions else None

    def fausses_dependances(nom, version, **_):
        return [Requirement(d) for d in INDEX[nom][version]]

    monkeypatch.setattr(pipeline.pypi, "derniere_version_mure", faux_choix)
    monkeypatch.setattr(pipeline.pypi, "dependances", fausses_dependances)


def enregistrees(base):
    return sorted((v.nom, v.version) for v in base.lister_versions())


@pytest.fixture
def base(tmp_path):
    return Base(str(tmp_path / "sas.db"))


def test_demander_enregistre_la_derniere_version_mure(base):
    v = pipeline.demander(Ecosysteme.PYPI, "demo", maintenant=MAINTENANT, base=base)
    assert (v.ecosysteme, v.nom, v.version, v.etat) == (Ecosysteme.PYPI, "demo", "1.1",
                                                        Etat.EN_ATTENTE)
    assert v.publiee_le == PUBLIEE and v.detectee_le == MAINTENANT
    assert base.lire_version(Ecosysteme.PYPI, "demo", "1.1") == v


def test_demander_accepte_le_texte_de_l_ecosysteme_et_normalise_le_nom(base):
    v = pipeline.demander("pypi", "Typing_Extensions", maintenant=MAINTENANT, base=base)
    assert (v.nom, v.version) == ("typing-extensions", "4.12")


def test_demander_sans_version_mure_leve_lookuperror(base):
    with pytest.raises(LookupError):
        pipeline.demander(Ecosysteme.PYPI, "absent", maintenant=MAINTENANT, base=base)
    assert base.lister_versions() == []


def test_demander_npm_hors_mvp(base):
    with pytest.raises(NotImplementedError):
        pipeline.demander(Ecosysteme.NPM, "left-pad", maintenant=MAINTENANT, base=base)


def test_la_page_web_de_a_appelle_le_vrai_demander(base, monkeypatch, tmp_path):
    """Intégration avec A : le web appelle demander(eco, nom), sans base ; on prend SAS_DB."""
    monkeypatch.setenv("SAS_DB", str(tmp_path / "sas.db"))
    client = TestClient(creer_app(base=base, mot_de_passe="mdp", secret="s"))
    client.post("/connexion", data={"identifiant": "admin", "mot_de_passe": "mdp"})
    r = client.post("/demander", data={"ecosysteme": "pypi", "nom": "demo"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert [(v.nom, v.version) for v in base.lister_versions()] == [("demo", "1.1")]


def test_demander_enregistre_aussi_les_dependances_transitives_en_attente(base):
    v = pipeline.demander(Ecosysteme.PYPI, "requests", maintenant=MAINTENANT, base=base)
    assert (v.nom, v.version) == ("requests", "2.34")
    assert enregistrees(base) == [("idna", "3.10"), ("requests", "2.34"), ("urllib3", "2.5")]
    assert {x.etat for x in base.lister_versions()} == {Etat.EN_ATTENTE}


def test_demander_supporte_un_cycle_de_dependances(base):
    pipeline.demander(Ecosysteme.PYPI, "cycle-a", maintenant=MAINTENANT, base=base)
    assert enregistrees(base) == [("cycle-a", "1.0"), ("cycle-b", "1.0")]


def test_une_dependance_introuvable_n_enregistre_rien(base):
    with pytest.raises(LookupError, match="absent"):
        pipeline.demander(Ecosysteme.PYPI, "casse", maintenant=MAINTENANT, base=base)
    assert enregistrees(base) == []


def test_trop_de_dependances_est_refuse(base, monkeypatch):
    monkeypatch.setattr(pipeline.demande, "MAX_PAQUETS", 2)
    with pytest.raises(ValueError, match="dépendances"):
        pipeline.demander(Ecosysteme.PYPI, "requests", maintenant=MAINTENANT, base=base)
    assert enregistrees(base) == []


def test_demander_prend_le_delai_de_sas_delai(base, monkeypatch):
    vus = []

    def faux_choix(nom, maintenant, *, delai, specifier=None, **_):
        vus.append(delai)
        return ("1.1", PUBLIEE)

    monkeypatch.setattr(pipeline.pypi, "derniere_version_mure", faux_choix)
    monkeypatch.setenv("SAS_DELAI", "120")
    pipeline.demander(Ecosysteme.PYPI, "demo", maintenant=MAINTENANT, base=base)
    assert vus == [timedelta(minutes=2)]


def test_le_message_d_erreur_donne_le_delai_de_la_demo(base, monkeypatch):
    monkeypatch.setenv("SAS_DELAI", "120")
    with pytest.raises(LookupError, match="120 s"):
        pipeline.demander(Ecosysteme.PYPI, "absent", maintenant=MAINTENANT, base=base)
