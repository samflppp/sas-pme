from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from commun.modeles import Ecosysteme, Etat, Niveau, Signal, Source, Version
from plateforme.db.acces import Base
from plateforme.web.app import creer_app

T0 = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
MDP = "mot-de-passe-de-test"
ECO = Ecosysteme.PYPI
FICHE = "/versions/pypi/colorama-utils/1.1"


@pytest.fixture
def base(tmp_path) -> Base:
    return Base(str(tmp_path / "sas.db"))


def connecte(base: Base, identifiant: str = "admin", mdp: str = MDP, **options) -> TestClient:
    c = TestClient(creer_app(base=base, mot_de_passe=MDP, secret="s", demander=lambda e, n: None,
                             **options))
    r = c.post("/connexion", data={"identifiant": identifiant, "mot_de_passe": mdp},
               follow_redirects=False)
    assert r.status_code == 303
    return c


def dev(base: Base) -> TestClient:
    connecte(base).post("/comptes", data={"identifiant": "mouabd", "role": "dev"})
    base.changer_mot_de_passe("mouabd", "un-mot-de-passe-long", acteur="test")
    return connecte(base, "mouabd", "un-mot-de-passe-long")


def version_a_revoir(base: Base) -> None:
    base.enregistrer_version(Version(ecosysteme=ECO, nom="colorama-utils", version="1.1",
                                     publiee_le=T0, detectee_le=T0, etat=Etat.EN_ATTENTE))
    base.ajouter_signal(Signal(ecosysteme=ECO, nom="colorama-utils", version="1.1",
                               source=Source.STATIQUE, niveau=Niveau.FORT, sorte="lit_secrets",
                               preuve={"fichier": "setup.py", "ligne": 38}))
    base.changer_etat(ECO, "colorama-utils", "1.1", Etat.A_REVOIR, "À revoir : lit_secrets.")


def decider(c: TestClient, decision: str, raison: str = "Lecture de la config, vérifiée à la main."):
    return c.post("/decision", data={"ecosysteme": "pypi", "nom": "colorama-utils",
                                     "version": "1.1", "decision": decision, "raison": raison},
                  follow_redirects=False)


def etat(base: Base) -> Etat:
    return base.fiche(ECO, "colorama-utils", "1.1").version.etat


@pytest.mark.parametrize("decision, attendu", [("approuvee", Etat.APPROUVEE),
                                               ("bloquee", Etat.BLOQUEE)])
def test_un_admin_tranche_une_version_a_revoir(base, decision, attendu):
    version_a_revoir(base)
    c = connecte(base)
    r = decider(c, decision)
    assert r.status_code == 303 and r.headers["location"] == FICHE
    assert etat(base) is attendu
    t = c.get(FICHE).text
    assert "admin : Lecture de la config, vérifiée à la main." in t  # la preuve dit qui et pourquoi
    dernier = base.journal()[-1]
    assert dernier.acteur == "admin" and dernier.charge["etat"] == attendu.value


def test_le_formulaire_n_apparait_que_pour_un_admin_sur_une_version_a_revoir(base):
    version_a_revoir(base)
    admin = connecte(base)
    assert 'action="/decision"' in admin.get(FICHE).text
    assert 'action="/decision"' not in dev(base).get(FICHE).text
    decider(admin, "approuvee")
    assert 'action="/decision"' not in admin.get(FICHE).text  # tranchée : plus de boutons


def test_un_dev_ne_peut_pas_trancher(base):
    version_a_revoir(base)
    assert decider(dev(base), "approuvee").status_code == 403
    assert etat(base) is Etat.A_REVOIR


def test_une_raison_est_obligatoire(base):
    version_a_revoir(base)
    r = decider(connecte(base), "approuvee", raison="   ")
    assert r.status_code == 400 and "raison est obligatoire" in r.text
    assert etat(base) is Etat.A_REVOIR


def test_un_refus_du_pipeline_se_dit_sur_la_fiche(base):
    version_a_revoir(base)
    c = connecte(base)
    decider(c, "bloquee")
    r = decider(c, "approuvee")  # déjà tranchée : le pipeline refuse
    assert r.status_code == 400 and "pas « à revoir »" in r.text
    assert "<h2>Preuves</h2>" in r.text
    assert etat(base) is Etat.BLOQUEE


def test_une_version_inconnue(base):
    assert decider(connecte(base), "approuvee").status_code == 404


def test_l_appel_au_pipeline(base):
    version_a_revoir(base)
    appels = []
    c = connecte(base, decider=lambda *a: appels.append(a))
    decider(c, "bloquee", raison="  Nom proche de colorama.  ")
    assert appels == [(base, ECO, "colorama-utils", "1.1", Etat.BLOQUEE,
                       "Nom proche de colorama.", "admin")]


def test_la_raison_ne_s_execute_pas(base):
    version_a_revoir(base)
    c = connecte(base)
    decider(c, "bloquee", raison="<script>alert(1)</script>")
    t = c.get(FICHE).text
    assert "<script>alert(1)</script>" not in t and "&lt;script&gt;" in t
