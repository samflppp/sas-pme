"""Demandes d'installation signées et journal d'accès (A pour C, conception-demo § 1) : la
plateforme demande au serveur d'installer un paquet ; le récepteur ne range qu'une demande signée,
le guichet la rend aux serveurs ; /v1/access rend les requêtes des serveurs à pypiserver."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from commun.modeles import Ecosysteme, Manifeste, canonique
from passerelle import guichet, installation
from passerelle.acces import requetes
from passerelle.recepteur import creer_app
from plateforme.signature import ed25519

MAINTENANT = datetime(2026, 10, 11, 9, 5, tzinfo=timezone.utc)


@pytest.fixture
def env(tmp_path):
    depot = tmp_path / "packages"
    depot.mkdir()
    cle = ed25519.generer_cle(tmp_path / "plateforme.pem")
    app = creer_app(depot, ed25519.cle_publique_pem(cle), tmp_path / "nonces.txt",
                    horloge=lambda: MAINTENANT, journal_acces=tmp_path / "acces.log",
                    installations=tmp_path / "installations.jsonl")
    return TestClient(app), cle, tmp_path


def demande(nom="demo-horodatage", nonce="c" * 32, age=timedelta(seconds=3), n=7):
    return installation.DemandeInstallation(nom=nom, demande=n, emis_le=MAINTENANT - age,
                                            nonce=nonce)


def poster(client, d, cle):
    t, sig = installation.signer(d, cle)
    return client.post("/v1/install", data={"demande": t, "signature": sig})


def test_une_demande_signee_est_rangee_et_le_guichet_la_rend(env):
    client, cle, tmp = env
    r = poster(client, demande(), cle)
    assert r.status_code == 201 and r.json() == {"n": 1, "nom": "demo-horodatage"}
    g = TestClient(guichet.creer_app(tmp / "installations.jsonl"))
    (e,) = g.get("/v1/installations").json()
    assert e["n"] == 1
    d = installation.verifier(e["demande"], e["signature"], ed25519.cle_publique_pem(cle),
                              MAINTENANT, set())
    assert d.nom == "demo-horodatage" and d.demande == 7
    assert g.get("/v1/installations?apres=1").json() == []


def test_une_demande_forgee_est_refusee_et_rien_n_est_range(env):
    client, _, tmp = env
    usurpateur = ed25519.generer_cle(tmp / "usurpateur.pem")
    assert poster(client, demande(), usurpateur).status_code == 401
    assert not (tmp / "installations.jsonl").exists()


def test_une_demande_rejouee_est_refusee(env):
    client, cle, _ = env
    assert poster(client, demande(), cle).status_code == 201
    assert poster(client, demande(), cle).status_code == 409


def test_une_demande_trop_vieille_est_refusee(env):
    client, cle, _ = env
    assert poster(client, demande(age=timedelta(minutes=11)), cle).status_code == 401


@pytest.mark.parametrize("nom", ["../etc", "-r /etc/passwd", "a b", "x; rm -rf /"])
def test_un_nom_qui_n_est_pas_un_paquet_est_refuse(env, nom):
    client, cle, _ = env
    d = installation.DemandeInstallation.model_construct(
        type="installation", ecosysteme="pypi", nom=nom, demande=1, emis_le=MAINTENANT,
        nonce="d" * 32)
    assert poster(client, d, cle).status_code == 400


def test_une_signature_de_manifeste_ne_vaut_pas_demande_d_installation(env):
    """Préfixe à part : la signature d'une publication ne peut pas être rejouée ici."""
    client, cle, _ = env
    m = Manifeste(type="revocation", ecosysteme=Ecosysteme.PYPI, nom="demo", version="1.0",
                  emis_le=MAINTENANT, nonce="e" * 32)
    r = client.post("/v1/install", data={"demande": canonique(m).decode(),
                                         "signature": ed25519.signer(m, cle)})
    assert r.status_code == 401


# --- le journal d'accès -----------------------------------------------------------------------
LIGNES = [
    "2026-10-11 09:00:00,123 Listening on 127.0.0.1:8080",
    '2026-10-11 09:00:01 10.42.2.20 - - "GET /simple/demo-horodatage/ HTTP/1.1"',
    '2026-10-11 09:00:02 10.42.2.20 - - "GET /packages/demo_horodatage-1.1-py3-none-any.whl HTTP/1.1"',
    '10.42.2.21 - - [11/Oct/2026:09:01:00 +0000] "GET /simple/requests/ HTTP/1.1" 200 512',
]


def test_les_requetes_gardent_leur_numero_de_ligne_et_sautent_le_reste():
    r = requetes(LIGNES)
    assert [x["n"] for x in r] == [2, 3, 4]
    assert r[0] == {"n": 2, "a": "2026-10-11 09:00:01", "ip": "10.42.2.20", "methode": "GET",
                    "chemin": "/simple/demo-horodatage/", "code": None}
    assert r[2]["code"] == 200 and r[2]["ip"] == "10.42.2.21"
    assert [x["n"] for x in requetes(LIGNES, apres=3)] == [4]


def test_la_route_access_rend_la_suite_du_journal(env):
    client, _, tmp = env
    (tmp / "acces.log").write_text("\n".join(LIGNES) + "\n", encoding="utf-8")
    r = client.get("/v1/access?apres=2").json()
    assert r["total"] == 4 and [x["n"] for x in r["lignes"]] == [3, 4]
