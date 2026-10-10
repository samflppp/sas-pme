"""pipeline.demander (B, M0) : choisit la dernière version mûre et l'enregistre en attente."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from commun.modeles import Ecosysteme, Etat
from plateforme import pipeline
from plateforme.db.acces import Base
from plateforme.web.app import creer_app

MAINTENANT = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
PUBLIEE = MAINTENANT - timedelta(days=5)


@pytest.fixture(autouse=True)
def faux_pypi(monkeypatch):
    def faux_choix(nom, maintenant, **_):
        return {"typing-extensions": ("4.12", PUBLIEE), "demo": ("1.1", PUBLIEE)}.get(nom)
    monkeypatch.setattr(pipeline.pypi, "derniere_version_mure", faux_choix)


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
