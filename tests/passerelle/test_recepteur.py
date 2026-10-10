"""Récepteur de la passerelle : API de docs/contrats.md § 4 (le TLS mutuel est posé par uvicorn)."""

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from commun.modeles import Ecosysteme, FichierManifeste, Manifeste, canonique
from passerelle.recepteur import creer_app
from plateforme.signature import ed25519

MAINTENANT = datetime(2026, 10, 11, 9, 5, tzinfo=timezone.utc)
ROUE = "requests-2.32.4-py3-none-any.whl"
CONTENU = b"une roue"


@pytest.fixture
def env(tmp_path):
    depot = tmp_path / "packages"
    depot.mkdir()
    cle = ed25519.generer_cle(tmp_path / "plateforme.pem")
    app = creer_app(depot, ed25519.cle_publique_pem(cle), tmp_path / "nonces.txt",
                    horloge=lambda: MAINTENANT)
    return TestClient(app), depot, cle, tmp_path


def _publication(nonce="a" * 32, contenu=CONTENU) -> Manifeste:
    return Manifeste(type="publication", ecosysteme=Ecosysteme.PYPI, nom="requests",
                     version="2.32.4", verdict_id=42, emis_le=MAINTENANT - timedelta(seconds=5),
                     nonce=nonce,
                     fichiers=[FichierManifeste(nom=ROUE, sha256=hashlib.sha256(contenu).hexdigest())])


def _revocation(nonce="b" * 32) -> Manifeste:
    return Manifeste(type="revocation", ecosysteme=Ecosysteme.PYPI, nom="requests",
                     version="2.32.4", emis_le=MAINTENANT, nonce=nonce, raison="signal tardif")


def _publier(client, m, cle, contenu=CONTENU):
    return client.post("/v1/publish",
                       data={"manifeste": canonique(m).decode(), "signature": ed25519.signer(m, cle)},
                       files=[("archives", (ROUE, contenu, "application/octet-stream"))])


def test_sante(env):
    client, *_ = env
    assert client.get("/v1/health").json() == {"pypi": True, "npm": False}


def test_publication_valide_ecrite_dans_le_depot(env):
    client, depot, cle, _ = env
    r = _publier(client, _publication(), cle)
    assert r.status_code == 201
    assert (depot / ROUE).read_bytes() == CONTENU


def test_publication_forgee_refusee_et_rien_n_est_ecrit(env):
    client, depot, _, tmp_path = env
    usurpateur = ed25519.generer_cle(tmp_path / "usurpateur.pem")
    r = _publier(client, _publication(), usurpateur)
    assert r.status_code == 401
    assert list(depot.iterdir()) == []


def test_archive_piegee_refusee(env):
    client, depot, cle, _ = env
    assert _publier(client, _publication(), cle, contenu=b"piegee").status_code == 400
    assert list(depot.iterdir()) == []


def test_rejeu_refuse_meme_apres_redemarrage(env):
    client, depot, cle, tmp_path = env
    m = _publication()
    assert _publier(client, m, cle).status_code == 201
    assert _publier(client, m, cle).status_code == 409
    relance = TestClient(creer_app(depot, ed25519.cle_publique_pem(cle), tmp_path / "nonces.txt",
                                   horloge=lambda: MAINTENANT))
    assert _publier(relance, m, cle).status_code == 409


def test_un_manifeste_de_revocation_ne_publie_pas(env):
    client, depot, cle, _ = env
    assert _publier(client, _revocation(), cle).status_code == 400
    assert list(depot.iterdir()) == []


def test_revocation_signee_retire_la_version(env):
    client, depot, cle, _ = env
    _publier(client, _publication(), cle)
    (depot / "requests-2.32.40-py3-none-any.whl").write_bytes(b"autre version")
    m = _revocation()
    r = client.post("/v1/revoke", data={"manifeste": canonique(m).decode(),
                                        "signature": ed25519.signer(m, cle)})
    assert r.status_code == 200
    assert sorted(p.name for p in depot.iterdir()) == ["requests-2.32.40-py3-none-any.whl"]


def test_revocation_forgee_refusee(env):
    client, depot, cle, tmp_path = env
    _publier(client, _publication(), cle)
    m = _revocation()
    autre = ed25519.generer_cle(tmp_path / "autre.pem")
    r = client.post("/v1/revoke", data={"manifeste": canonique(m).decode(),
                                        "signature": ed25519.signer(m, autre)})
    assert r.status_code == 401
    assert (depot / ROUE).exists()


def test_une_publication_ne_sert_pas_de_revocation(env):
    client, depot, cle, _ = env
    m = _publication()
    _publier(client, m, cle)
    m2 = _publication(nonce="c" * 32)
    m2 = Manifeste(**{**m2.model_dump(), "fichiers": []})
    r = client.post("/v1/revoke", data={"manifeste": canonique(m2).decode(),
                                        "signature": ed25519.signer(m2, cle)})
    assert r.status_code == 400
    assert (depot / ROUE).exists()


def test_inventaire_vide_sans_journal(env):
    client, *_ = env
    # creer_app sans journal_acces : la route répond [] (défaut).
    assert client.get("/v1/inventory").json() == []


def test_inventaire_lit_le_journal_et_joint_les_machines(tmp_path):
    depot = tmp_path / "packages"
    depot.mkdir()
    (depot / "requests-2.32.4-py3-none-any.whl").write_bytes(b"x")   # présente : le GET a réussi
    cle = ed25519.generer_cle(tmp_path / "plateforme.pem")
    journal = tmp_path / "acces.log"
    journal.write_text(
        '10.42.2.20 - - [11/Oct/2026:09:00:01 +0000] '
        '"GET /packages/requests-2.32.4-py3-none-any.whl HTTP/1.1" 200 100\n'
        '10.42.2.20 - - [11/Oct/2026:09:00:00 +0000] "GET /simple/requests/ HTTP/1.1" 200 500\n',
        encoding="utf-8",
    )
    app = creer_app(depot, ed25519.cle_publique_pem(cle), tmp_path / "nonces.txt",
                    horloge=lambda: MAINTENANT, journal_acces=journal)
    inv = TestClient(app).get("/v1/inventory").json()
    assert len(inv) == 1
    assert inv[0]["nom"] == "requests"
    assert inv[0]["version"] == "2.32.4"
    assert inv[0]["telechargements"] == 1
    assert inv[0]["ecosysteme"] == "pypi"
    assert inv[0]["machines"] == ["10.42.2.20"]   # hors contrat EntreeInventaire


def test_inventaire_suit_publications_et_revocations(tmp_path):
    """De bout en bout : publié puis téléchargé, révoqué ensuite → toujours listé (PR #38)."""
    depot = tmp_path / "packages"
    depot.mkdir()
    cle = ed25519.generer_cle(tmp_path / "plateforme.pem")
    journal = tmp_path / "acces.log"
    maintenant = [MAINTENANT]                               # horloge réglable du récepteur
    app = creer_app(depot, ed25519.cle_publique_pem(cle), tmp_path / "nonces.txt",
                    horloge=lambda: maintenant[0],
                    journal_acces=journal, registre=tmp_path / "registre.txt")
    client = TestClient(app)
    assert _publier(client, _publication(), cle).status_code == 201
    def get(minutes):        # ligne du journal de pypiserver, MAINTENANT + minutes
        quand = (MAINTENANT + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        return f'{quand},000 10.42.2.20 - - "GET /packages/{ROUE} HTTP/1.1"\n'

    # avant la publication (404) ; après (200) ; après la révocation (404)
    journal.write_text(get(-1) + get(1) + get(6))
    maintenant[0] = MAINTENANT + timedelta(minutes=5)
    m = Manifeste(**{**_revocation().model_dump(), "emis_le": maintenant[0]})
    assert client.post("/v1/revoke", data={"manifeste": canonique(m).decode(),
                                           "signature": ed25519.signer(m, cle)}).status_code == 200
    assert client.get("/v1/inventory").json() == [
        {"ecosysteme": "pypi", "nom": "requests", "version": "2.32.4", "telechargements": 1,
         "dernier": (MAINTENANT + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "machines": ["10.42.2.20"]}]


def test_revocation_retire_roue_et_sdist_et_repond_200_meme_si_deja_absente(env):
    """Demande de A (point A-revocation) : la wheel ET le sdist partent ; une révocation rejouée
    sur une version déjà absente répond quand même 200 (rien à retirer)."""
    client, depot, cle, _ = env
    _publier(client, _publication(), cle)
    (depot / "requests-2.32.4.tar.gz").write_bytes(b"sdist")          # sdist posé à côté
    (depot / "Requests-2.32.4.zip").write_bytes(b"ancien sdist")      # casse différente
    m = _revocation()
    r = client.post("/v1/revoke", data={"manifeste": canonique(m).decode(),
                                        "signature": ed25519.signer(m, cle)})
    assert r.status_code == 200
    assert sorted(r.json()["retire"]) == ["Requests-2.32.4.zip", ROUE, "requests-2.32.4.tar.gz"]
    assert list(depot.iterdir()) == []
    m2 = _revocation(nonce="d" * 32)                                  # nouveau nonce, déjà absente
    r2 = client.post("/v1/revoke", data={"manifeste": canonique(m2).decode(),
                                         "signature": ed25519.signer(m2, cle)})
    assert (r2.status_code, r2.json()["retire"]) == (200, [])
