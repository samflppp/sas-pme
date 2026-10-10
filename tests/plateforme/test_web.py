from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from commun.modeles import Ecosysteme, Etat, Verdict, Version
from plateforme.db.acces import Base
from plateforme.web.app import creer_app

T0 = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
MDP = "mot-de-passe-de-test"


@pytest.fixture
def base(tmp_path) -> Base:
    return Base(str(tmp_path / "sas.db"))


@pytest.fixture
def demandes() -> list:
    return []


@pytest.fixture
def client(base, demandes) -> TestClient:
    app = creer_app(base=base, mot_de_passe=MDP, secret="secret-de-test",
                    demander=lambda eco, nom: demandes.append((eco, nom)))
    return TestClient(app)


def connecter(client: TestClient) -> None:
    r = client.post("/connexion", data={"identifiant": "admin", "mot_de_passe": MDP},
                    follow_redirects=False)
    assert r.status_code == 303


def test_sans_connexion_on_est_renvoye_vers_la_page_de_connexion(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/connexion"
    assert client.get("/sante").json() == {"ok": True}


def test_mauvais_mot_de_passe_refuse(client):
    r = client.post("/connexion", data={"identifiant": "admin", "mot_de_passe": "faux"},
                    follow_redirects=False)
    assert r.status_code == 401
    assert client.get("/", follow_redirects=False).status_code == 303


def test_connexion_puis_catalogue_vide(client):
    connecter(client)
    r = client.get("/")
    assert r.status_code == 200
    assert "Aucune version" in r.text


def test_le_catalogue_montre_les_versions_et_leur_etat(client, base):
    base.enregistrer_version(Version(ecosysteme=Ecosysteme.PYPI, nom="requests", version="2.32.4",
                                     publiee_le=T0, detectee_le=T0, etat=Etat.PUBLIEE))
    connecter(client)
    r = client.get("/")
    assert "requests" in r.text and "2.32.4" in r.text and "publiee" in r.text


def test_demander_un_paquet_appelle_le_pipeline_et_journalise(client, base, demandes):
    connecter(client)
    r = client.post("/demander", data={"ecosysteme": "pypi", "nom": "requests"}, follow_redirects=False)
    assert r.status_code == 303
    assert demandes == [(Ecosysteme.PYPI, "requests")]
    assert [e.action for e in base.journal()] == ["connexion", "demande_paquet"]


def test_un_nom_de_paquet_invalide_est_refuse(client, demandes):
    connecter(client)
    r = client.post("/demander", data={"ecosysteme": "pypi", "nom": "../../etc/passwd"},
                    follow_redirects=False)
    assert r.status_code == 400 and demandes == []


def test_la_fiche_d_une_version(client, base):
    base.enregistrer_version(Version(ecosysteme=Ecosysteme.PYPI, nom="reqeusts", version="1.0",
                                     publiee_le=T0, detectee_le=T0, etat=Etat.EN_ANALYSE))
    base.enregistrer_verdict(Ecosysteme.PYPI, "reqeusts", "1.0",
                             Verdict(etat=Etat.BLOQUEE, raison="Typosquat de requests.", signaux=[]))
    connecter(client)
    r = client.get("/versions/pypi/reqeusts/1.0")
    assert r.status_code == 200 and "Typosquat de requests." in r.text
    assert client.get("/versions/pypi/inconnu/1.0").status_code == 404


def test_deconnexion(client):
    connecter(client)
    client.post("/deconnexion")
    assert client.get("/", follow_redirects=False).status_code == 303
