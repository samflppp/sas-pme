"""Côté plateforme (A pour C) : demander une installation au serveur, signée, et lire le journal
d'accès de la passerelle. Branché sur le vrai récepteur, comme test_signature_m1."""
import pytest
from fastapi.testclient import TestClient

from passerelle import guichet, installation
from passerelle.recepteur import creer_app
from plateforme import signature
from plateforme.signature import ed25519


@pytest.fixture
def passerelle(tmp_path, monkeypatch):
    cle = tmp_path / "signature.pem"
    publique = ed25519.cle_publique_pem(ed25519.generer_cle(cle))
    (tmp_path / "packages").mkdir()
    (tmp_path / "acces.log").write_text(
        '2026-10-11 09:00:01 10.42.2.20 - - "GET /simple/demo-horodatage/ HTTP/1.1"\n',
        encoding="utf-8")
    app = creer_app(tmp_path / "packages", publique, tmp_path / "nonces.txt",
                    journal_acces=tmp_path / "acces.log",
                    installations=tmp_path / "installations.jsonl")
    monkeypatch.setenv("SAS_PASSERELLE_URL", "https://10.42.2.10:8443")
    monkeypatch.setenv("SAS_CLE_SIGNATURE", str(cle))
    monkeypatch.setattr(signature, "_client", lambda: TestClient(app, base_url="https://passerelle"))
    return tmp_path, publique


def test_la_demande_d_installation_arrive_signee_au_guichet(passerelle):
    tmp, publique = passerelle
    assert signature.demander_installation("pypi", "demo-horodatage", 12) == 1
    (e,) = TestClient(guichet.creer_app(tmp / "installations.jsonl")).get(
        "/v1/installations").json()
    from datetime import datetime, timezone
    d = installation.verifier(e["demande"], e["signature"], publique, datetime.now(timezone.utc),
                              set())
    assert (d.nom, d.demande) == ("demo-horodatage", 12)
    assert signature.demander_installation("pypi", "demo-horodatage", 13) == 2   # nonce neuf


def test_un_nom_invalide_ne_part_pas(passerelle):
    with pytest.raises(ValueError):
        signature.demander_installation("pypi", "--index-url=http://x", 1)


def test_npm_n_est_pas_pris_en_charge(passerelle):
    with pytest.raises(NotImplementedError):
        signature.demander_installation("npm", "left-pad", 1)


def test_lire_acces_rend_la_suite_du_journal(passerelle):
    r = signature.lire_acces(0)
    assert r["total"] == 1 and r["lignes"][0]["chemin"] == "/simple/demo-horodatage/"
    assert signature.lire_acces(1)["lignes"] == []


def test_sans_passerelle_rien_n_est_demande(monkeypatch):
    monkeypatch.delenv("SAS_PASSERELLE_URL", raising=False)
    with pytest.raises(RuntimeError, match="passerelle"):
        signature.demander_installation("pypi", "demo-horodatage", 1)
    with pytest.raises(RuntimeError, match="passerelle"):
        signature.lire_acces(0)
