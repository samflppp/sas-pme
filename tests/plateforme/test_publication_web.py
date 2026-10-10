from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from commun.modeles import Ecosysteme, Etat, Verdict, Version
from plateforme.db.acces import Base
from plateforme.web.app import creer_app, etat_publication

T0 = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
MDP = "mot-de-passe-de-test"
ECO = Ecosysteme.PYPI
FICHE = "/versions/pypi/demo-horodatage/1.1"


@pytest.fixture
def base(tmp_path) -> Base:
    return Base(str(tmp_path / "sas.db"))


def client(base: Base) -> TestClient:
    c = TestClient(creer_app(base=base, mot_de_passe=MDP, secret="s", demander=lambda e, n: None))
    c.post("/connexion", data={"identifiant": "admin", "mot_de_passe": MDP})
    return c


def approuvee(base: Base, raison: str) -> None:
    """Ce que traiter() (B) écrit quand publier() (C) échoue : la version reste approuvée."""
    base.enregistrer_version(Version(ecosysteme=ECO, nom="demo-horodatage", version="1.1",
                                     publiee_le=T0, detectee_le=T0, etat=Etat.EN_ATTENTE))
    base.enregistrer_verdict(ECO, "demo-horodatage", "1.1", Verdict(
        etat=Etat.APPROUVEE, raison="Aucun signal fort ni bloquant.", signaux=[]))
    base.changer_etat(ECO, "demo-horodatage", "1.1", Etat.APPROUVEE, raison)


@pytest.mark.parametrize("raison, attendu", [
    ("publication échouée : passerelle 401 : signature invalide",
     {"sorte": "refus", "code": "401", "motif": "signature invalide"}),
    ("publication échouée : passerelle 409 : nonce déjà vu",
     {"sorte": "refus", "code": "409", "motif": "nonce déjà vu"}),
    ("publication échouée : [Errno 111] Connection refused",
     {"sorte": "panne", "motif": "[Errno 111] Connection refused"}),
    ("Aucun signal fort ni bloquant.", None),
    ("signée et publiée dans la passerelle", None),
])
def test_lire_l_echec_de_publication(raison, attendu):
    assert etat_publication(Etat.APPROUVEE, raison) == attendu


def test_seule_une_version_approuvee_est_en_echec_de_publication():
    raison = "publication échouée : passerelle 401 : signature invalide"
    assert etat_publication(Etat.PUBLIEE, raison) is None


def test_un_refus_de_la_passerelle_se_voit_sur_la_fiche(base):
    approuvee(base, "publication échouée : passerelle 401 : signature invalide")
    t = client(base).get(FICHE).text
    assert "Refusée par la passerelle" in t and "401" in t and "signature invalide" in t
    assert 'class="raison ko publication"' in t
    assert "Passerelle injoignable" not in t


def test_une_panne_reseau_se_dit_autrement(base):
    approuvee(base, "publication échouée : [Errno 111] Connection refused")
    t = client(base).get(FICHE).text
    assert "Passerelle injoignable" in t and "retentée au tour suivant" in t
    assert "Refusée par la passerelle" not in t


def test_un_motif_venu_de_la_passerelle_ne_s_execute_pas(base):
    approuvee(base, "publication échouée : passerelle 400 : <script>alert(1)</script>")
    t = client(base).get(FICHE).text
    assert "<script>alert(1)</script>" not in t and "&lt;script&gt;" in t
