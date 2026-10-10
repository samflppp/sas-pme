import re

import pytest
from fastapi.testclient import TestClient

from plateforme.db.acces import Base, Role
from plateforme.web.app import creer_app

MDP = "mot-de-passe-de-test"
NOUVEAU = "un-nouveau-mot-de-passe"


@pytest.fixture
def base(tmp_path) -> Base:
    return Base(str(tmp_path / "sas.db"))


def client_de(base: Base) -> TestClient:
    return TestClient(creer_app(base=base, mot_de_passe=MDP, secret="s", demander=lambda e, n: None))


def connecter(client: TestClient, identifiant: str, mdp: str) -> None:
    r = client.post("/connexion", data={"identifiant": identifiant, "mot_de_passe": mdp},
                    follow_redirects=False)
    assert r.status_code == 303, r.text


def creer_dev(admin: TestClient, identifiant: str = "mouabd", role: str = "dev") -> str:
    """Crée le compte depuis la page Comptes ; renvoie le mot de passe affiché une fois."""
    r = admin.post("/comptes", data={"identifiant": identifiant, "role": role})
    assert r.status_code == 200, r.text
    return re.search(r'data-mot-de-passe="([^"]+)"', r.text).group(1)


def test_au_premier_lancement_le_compte_admin_est_cree(base):
    client_de(base)
    (c,) = base.lister_comptes()
    assert (c.identifiant, c.role, c.doit_changer) == ("admin", Role.ADMIN, False)
    # relancer l'application ne recrée rien et ne change pas le mot de passe
    client_de(base)
    assert len(base.lister_comptes()) == 1


def test_l_admin_cree_un_compte_dev_avec_un_mot_de_passe_affiche_une_fois(base):
    admin = client_de(base)
    connecter(admin, "admin", MDP)
    mdp = creer_dev(admin)
    assert len(mdp) >= 16
    assert base.lire_compte("mouabd").role is Role.DEV
    assert mdp not in admin.get("/comptes").text  # plus jamais affiché
    assert ("admin", "compte_cree", "compte:mouabd") in [
        (e.acteur, e.action, e.sujet) for e in base.journal()]


def test_un_nouveau_compte_doit_changer_son_mot_de_passe_avant_tout(base):
    admin = client_de(base)
    connecter(admin, "admin", MDP)
    mdp = creer_dev(admin)
    dev = client_de(base)
    connecter(dev, "mouabd", mdp)
    r = dev.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/mot-de-passe"
    r = dev.post("/mot-de-passe", data={"actuel": mdp, "nouveau": NOUVEAU, "confirmation": NOUVEAU},
                 follow_redirects=False)
    assert r.status_code == 303
    assert dev.get("/").status_code == 200


@pytest.mark.parametrize("actuel, nouveau, confirmation, attendu", [
    ("faux", NOUVEAU, NOUVEAU, "actuel est incorrect"),
    (MDP, "court", "court", "au moins 12"),
    (MDP, NOUVEAU, NOUVEAU + "x", "ne correspondent pas"),
])
def test_changer_son_mot_de_passe_refuse_les_erreurs(base, actuel, nouveau, confirmation, attendu):
    admin = client_de(base)
    connecter(admin, "admin", MDP)
    r = admin.post("/mot-de-passe",
                   data={"actuel": actuel, "nouveau": nouveau, "confirmation": confirmation})
    assert r.status_code == 400 and attendu in r.text
    assert base.authentifier("admin", MDP) is not None


def test_un_dev_n_accede_pas_aux_comptes(base):
    admin = client_de(base)
    connecter(admin, "admin", MDP)
    mdp = creer_dev(admin)
    base.changer_mot_de_passe("mouabd", NOUVEAU, acteur="test")
    dev = client_de(base)
    connecter(dev, "mouabd", NOUVEAU)
    assert dev.get("/comptes").status_code == 403
    assert dev.post("/comptes", data={"identifiant": "pirate", "role": "admin"}).status_code == 403
    assert dev.post("/comptes/mouabd/role", data={"role": "admin"}).status_code == 403
    assert base.lire_compte("pirate") is None and base.lire_compte("mouabd").role is Role.DEV
    assert "Comptes" not in dev.get("/").text and "Comptes" in admin.get("/").text
    assert mdp  # utilisé


def test_desactiver_coupe_aussi_la_session_en_cours(base):
    admin = client_de(base)
    connecter(admin, "admin", MDP)
    creer_dev(admin)
    base.changer_mot_de_passe("mouabd", NOUVEAU, acteur="test")
    dev = client_de(base)
    connecter(dev, "mouabd", NOUVEAU)
    assert dev.get("/").status_code == 200
    assert admin.post("/comptes/mouabd/desactiver", follow_redirects=False).status_code == 303
    r = dev.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/connexion"
    r = dev.post("/connexion", data={"identifiant": "mouabd", "mot_de_passe": NOUVEAU})
    assert r.status_code == 401


def test_changer_le_role_prend_effet_tout_de_suite(base):
    admin = client_de(base)
    connecter(admin, "admin", MDP)
    creer_dev(admin)
    base.changer_mot_de_passe("mouabd", NOUVEAU, acteur="test")
    dev = client_de(base)
    connecter(dev, "mouabd", NOUVEAU)
    assert dev.get("/comptes").status_code == 403
    assert admin.post("/comptes/mouabd/role", data={"role": "admin"},
                      follow_redirects=False).status_code == 303
    assert dev.get("/comptes").status_code == 200


def test_l_admin_ne_peut_pas_retirer_le_dernier_admin(base):
    admin = client_de(base)
    connecter(admin, "admin", MDP)
    r = admin.post("/comptes/admin/desactiver")
    assert r.status_code == 400 and "au moins un admin" in r.text
    r = admin.post("/comptes/admin/role", data={"role": "dev"})
    assert r.status_code == 400
    assert base.lire_compte("admin").actif and base.lire_compte("admin").role is Role.ADMIN


@pytest.mark.parametrize("identifiant, role", [
    ("Mouabd", "dev"), ("a", "dev"), ("x/../y", "dev"), ("mouabd", "root"), ("admin", "dev"),
])
def test_creation_refusee(base, identifiant, role):
    admin = client_de(base)
    connecter(admin, "admin", MDP)
    r = admin.post("/comptes", data={"identifiant": identifiant, "role": role})
    assert r.status_code == 400
    assert len(base.lister_comptes()) == 1


def test_compte_inconnu(base):
    admin = client_de(base)
    connecter(admin, "admin", MDP)
    assert admin.post("/comptes/inconnu/desactiver").status_code == 404
    assert admin.post("/comptes/inconnu/role", data={"role": "dev"}).status_code == 404
