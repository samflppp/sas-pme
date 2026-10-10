from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from commun.modeles import Ecosysteme, Etat, Version
from plateforme.db.acces import Base
from plateforme.signature import PublicationRefusee
from plateforme.web.app import creer_app

T0 = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
MDP = "mot-de-passe-de-test"
ECO = Ecosysteme.PYPI
FICHE = "/versions/pypi/demo-horodatage/1.1"
RAISON = "Avis GHSA publié après coup : le mainteneur a été compromis."


@pytest.fixture
def base(tmp_path) -> Base:
    return Base(str(tmp_path / "sas.db"))


def connecte(base: Base, identifiant: str = "admin", mdp: str = MDP, **options) -> TestClient:
    options.setdefault("revoquer", lambda *a: None)
    c = TestClient(creer_app(base=base, mot_de_passe=MDP, secret="s", demander=lambda e, n: None,
                             **options))
    r = c.post("/connexion", data={"identifiant": identifiant, "mot_de_passe": mdp},
               follow_redirects=False)
    assert r.status_code == 303
    return c


def dev(base: Base, **options) -> TestClient:
    connecte(base).post("/comptes", data={"identifiant": "mouabd", "role": "dev"})
    base.changer_mot_de_passe("mouabd", "un-mot-de-passe-long", acteur="test")
    return connecte(base, "mouabd", "un-mot-de-passe-long", **options)


def version(base: Base, etat: Etat = Etat.PUBLIEE) -> None:
    base.enregistrer_version(Version(ecosysteme=ECO, nom="demo-horodatage", version="1.1",
                                     publiee_le=T0, detectee_le=T0, etat=Etat.EN_ATTENTE))
    base.changer_etat(ECO, "demo-horodatage", "1.1", etat, "Publiée sur le dépôt interne.")


def revoquer(c: TestClient, raison: str = RAISON, nom: str = "demo-horodatage"):
    return c.post("/revocation", data={"ecosysteme": "pypi", "nom": nom, "version": "1.1",
                                       "raison": raison}, follow_redirects=False)


def etat(base: Base) -> Etat:
    return base.fiche(ECO, "demo-horodatage", "1.1").version.etat


def test_un_admin_revoque_une_version_publiee(base):
    version(base)
    appels = []
    c = connecte(base, revoquer=lambda *a: appels.append(a))
    r = revoquer(c, raison=f"  {RAISON}  ")
    assert r.status_code == 303 and r.headers["location"] == FICHE
    assert appels == [(ECO, "demo-horodatage", "1.1", RAISON)]   # la passerelle d'abord
    assert etat(base) is Etat.REVOQUEE
    dernier = base.journal()[-1]
    assert dernier.acteur == "admin" and dernier.charge["etat"] == "revoquee"
    assert RAISON in dernier.charge["raison"]
    assert RAISON in c.get(FICHE).text


def test_le_formulaire_n_apparait_que_pour_un_admin_sur_une_version_publiee(base):
    version(base)
    admin = connecte(base)
    assert 'action="/revocation"' in admin.get(FICHE).text
    assert 'action="/revocation"' not in dev(base).get(FICHE).text
    revoquer(admin)
    assert 'action="/revocation"' not in admin.get(FICHE).text   # déjà révoquée


@pytest.mark.parametrize("etat_initial", [Etat.APPROUVEE, Etat.BLOQUEE, Etat.A_REVOIR,
                                          Etat.REVOQUEE])
def test_seule_une_version_publiee_se_revoque(base, etat_initial):
    version(base, etat_initial)
    appels = []
    c = connecte(base, revoquer=lambda *a: appels.append(a))
    assert 'action="/revocation"' not in c.get(FICHE).text
    r = revoquer(c)
    assert r.status_code == 400 and "pas publiée" in r.text
    assert appels == [] and etat(base) is etat_initial


def test_un_dev_ne_peut_pas_revoquer(base):
    version(base)
    appels = []
    r = revoquer(dev(base, revoquer=lambda *a: appels.append(a)))
    assert r.status_code == 403
    assert appels == [] and etat(base) is Etat.PUBLIEE


def test_une_raison_est_obligatoire(base):
    version(base)
    appels = []
    r = revoquer(connecte(base, revoquer=lambda *a: appels.append(a)), raison="   ")
    assert r.status_code == 400 and "raison est obligatoire" in r.text
    assert appels == [] and etat(base) is Etat.PUBLIEE


def test_la_raison_est_bornee(base):
    version(base)
    appels = []
    revoquer(connecte(base, revoquer=lambda *a: appels.append(a)), raison="x" * 2000)
    assert len(appels[0][3]) == 500


def _refus(*a):
    raise PublicationRefusee("passerelle 401 : signature invalide")


def _panne(*a):
    raise OSError("connexion refusée")


@pytest.mark.parametrize("echec, attendu", [(_refus, "passerelle 401 : signature invalide"),
                                            (_panne, "connexion refusée")])
def test_un_echec_de_la_passerelle_laisse_la_version_publiee(base, echec, attendu):
    version(base)
    c = connecte(base, revoquer=echec)
    r = revoquer(c)
    assert r.status_code == 502
    assert "Révocation échouée" in r.text and attendu in r.text
    assert etat(base) is Etat.PUBLIEE                  # rien n'a changé : on peut réessayer
    assert 'action="/revocation"' in r.text
    dernier = base.journal()[-1]
    assert dernier.action == "revocation_echouee" and dernier.acteur == "admin"


def test_une_version_inconnue(base):
    assert revoquer(connecte(base)).status_code == 404


def test_la_raison_ne_s_execute_pas(base):
    version(base)
    c = connecte(base)
    revoquer(c, raison="<script>alert(1)</script>")
    t = c.get(FICHE).text
    assert "<script>alert(1)</script>" not in t and "&lt;script&gt;" in t
