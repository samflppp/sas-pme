"""M1 : publier / revoquer / lire_inventaire en POST signé vers le vrai récepteur de la passerelle.

Le TLS mutuel est remplacé par un client de test branché directement sur l'application du récepteur.
"""

import pytest
from fastapi.testclient import TestClient

from commun.modeles import Ecosysteme
from passerelle.recepteur import creer_app
from plateforme import signature
from plateforme.signature import ed25519

ROUE = "requests-2.32.4-py3-none-any.whl"


@pytest.fixture
def passerelle(tmp_path, monkeypatch):
    """Une passerelle qui connaît la clé publique de la plateforme ; la plateforme a sa clé privée."""
    depot = tmp_path / "packages"
    depot.mkdir()
    cle = tmp_path / "signature.pem"
    publique = ed25519.cle_publique_pem(ed25519.generer_cle(cle))
    app = creer_app(depot, publique, tmp_path / "nonces.txt")
    monkeypatch.setenv("SAS_PASSERELLE_URL", "https://10.42.2.10:8443")
    monkeypatch.setenv("SAS_CLE_SIGNATURE", str(cle))
    monkeypatch.setattr(signature, "_client", lambda: TestClient(app, base_url="https://passerelle"))
    return depot


def _roue(tmp_path, contenu=b"une roue"):
    a = tmp_path / ROUE
    a.write_bytes(contenu)
    return a


def test_publier_signe_et_la_passerelle_ecrit_l_archive(tmp_path, passerelle):
    signature.publier(Ecosysteme.PYPI, "requests", "2.32.4", [_roue(tmp_path)], 42)
    assert (passerelle / ROUE).read_bytes() == b"une roue"


def test_une_plateforme_usurpee_est_refusee(tmp_path, passerelle, monkeypatch):
    fausse = tmp_path / "usurpateur.pem"
    ed25519.generer_cle(fausse)
    monkeypatch.setenv("SAS_CLE_SIGNATURE", str(fausse))
    with pytest.raises(signature.PublicationRefusee, match="401"):
        signature.publier(Ecosysteme.PYPI, "requests", "2.32.4", [_roue(tmp_path)], 42)
    assert list(passerelle.iterdir()) == []


def test_publier_deux_fois_tire_deux_nonces(tmp_path, passerelle):
    roue = _roue(tmp_path)
    signature.publier(Ecosysteme.PYPI, "requests", "2.32.4", [roue], 42)
    signature.publier(Ecosysteme.PYPI, "requests", "2.32.4", [roue], 42)    # pas de 409


def test_publier_verifie_les_archives_avant_d_envoyer(tmp_path, passerelle):
    with pytest.raises(FileNotFoundError):
        signature.publier(Ecosysteme.PYPI, "requests", "2.32.4", [tmp_path / "absente.whl"], 42)
    with pytest.raises(ValueError):
        signature.publier(Ecosysteme.PYPI, "requests", "2.32.4", [], 42)


def test_revoquer_retire_la_version(tmp_path, passerelle):
    signature.publier(Ecosysteme.PYPI, "requests", "2.32.4", [_roue(tmp_path)], 42)
    signature.revoquer(Ecosysteme.PYPI, "requests", "2.32.4", "signal tardif")
    assert list(passerelle.iterdir()) == []


def test_lire_inventaire_interroge_la_passerelle(passerelle):
    assert signature.lire_inventaire() == []


def test_sans_url_on_reste_sur_le_stub_scp(tmp_path, monkeypatch):
    monkeypatch.delenv("SAS_PASSERELLE_URL", raising=False)
    monkeypatch.setenv("SAS_PASSERELLE_SSH", "ubuntu@10.42.2.10")
    monkeypatch.setenv("SAS_PUBLICATION_NON_SIGNEE", "oui-tests")
    lancees = []
    monkeypatch.setattr(signature.subprocess, "run", lambda cmd, **k: lancees.append(cmd))
    signature.publier(Ecosysteme.PYPI, "requests", "2.32.4", [_roue(tmp_path)], 42)
    assert lancees[0][0] == "scp"


def test_lire_inventaire_accepte_la_vraie_route_meme_avec_des_champs_hors_contrat(tmp_path, monkeypatch):
    """La route /v1/inventory joint `machines` (hors EntreeInventaire, extra=forbid) : la plateforme
    doit l'ignorer au lieu de lever (relecture de A sur la PR #39)."""
    depot = tmp_path / "packages"
    depot.mkdir()
    (depot / ROUE).write_bytes(b"une roue")
    journal = tmp_path / "pypiserver-acces.log"
    journal.write_text(f'2026-10-10 20:16:28,293 10.42.2.20 - - "GET /packages/{ROUE} HTTP/1.1"\n')
    cle = tmp_path / "signature.pem"
    app = creer_app(depot, ed25519.cle_publique_pem(ed25519.generer_cle(cle)),
                    tmp_path / "nonces.txt", journal_acces=journal)
    monkeypatch.setenv("SAS_PASSERELLE_URL", "https://10.42.2.10:8443")
    monkeypatch.setattr(signature, "_client", lambda: TestClient(app, base_url="https://passerelle"))
    brut = TestClient(app).get("/v1/inventory").json()
    assert brut[0]["machines"] == ["10.42.2.20"]            # la route garde le champ en plus
    [entree] = signature.lire_inventaire()
    assert (entree.nom, entree.version, entree.telechargements) == ("requests", "2.32.4", 1)


# --- npm : la même publication signée, vers le Verdaccio de la passerelle ----------------------
class FauxVerdaccio:
    def __init__(self):
        self.publies, self.retires = [], []

    def publier(self, nom, version, fichier, tgz):
        self.publies.append((nom, version, fichier, tgz))

    def retirer(self, nom, version):
        self.retires.append((nom, version))
        return [f"{nom.split('/')[-1]}-{version}.tgz"]

    def disponible(self):
        return True


@pytest.fixture
def passerelle_npm(tmp_path, monkeypatch):
    depot = tmp_path / "packages"
    depot.mkdir()
    cle = tmp_path / "signature.pem"
    publique = ed25519.cle_publique_pem(ed25519.generer_cle(cle))
    vd = FauxVerdaccio()
    app = creer_app(depot, publique, tmp_path / "nonces.txt", depot_npm=vd)
    monkeypatch.setenv("SAS_PASSERELLE_URL", "https://10.42.2.10:8443")
    monkeypatch.setenv("SAS_CLE_SIGNATURE", str(cle))
    monkeypatch.setattr(signature, "_client", lambda: TestClient(app, base_url="https://passerelle"))
    return vd


def test_npm_publier_et_revoquer_signes_passent_par_verdaccio(tmp_path, passerelle_npm):
    tgz = tmp_path / "outil-1.0.0.tgz"
    tgz.write_bytes(b"archive npm")
    signature.publier(Ecosysteme.NPM, "@org/outil", "1.0.0", [tgz], 7)
    assert passerelle_npm.publies == [("@org/outil", "1.0.0", "outil-1.0.0.tgz", b"archive npm")]
    signature.revoquer(Ecosysteme.NPM, "@org/outil", "1.0.0", "signal tardif")
    assert passerelle_npm.retires == [("@org/outil", "1.0.0")]


def test_npm_un_nom_dangereux_est_refuse_avant_tout_envoi(passerelle_npm):
    with pytest.raises(ValueError):
        signature.revoquer(Ecosysteme.NPM, "@org/../x", "1.0.0", "x")
    assert passerelle_npm.retires == []
