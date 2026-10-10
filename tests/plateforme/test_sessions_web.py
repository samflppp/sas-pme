"""A5 (relecture de B) : origine des POST vérifiée, sessions coupées par un changement de mot de
passe, mot de passe admin initial soumis à MDP_MIN."""
import pytest
from fastapi.testclient import TestClient

from plateforme.db.acces import Base
from plateforme.web import app as module_app
from plateforme.web.app import MDP_MIN, creer_app

MDP = "mot-de-passe-de-test"
NOUVEAU = "un-nouveau-mot-de-passe"
ICI = "http://testserver"           # l'origine des requêtes du TestClient


@pytest.fixture
def base(tmp_path) -> Base:
    return Base(str(tmp_path / "sas.db"))


def client_de(base: Base) -> TestClient:
    return TestClient(creer_app(base=base, mot_de_passe=MDP, secret="s", demander=lambda e, n: None))


def connecte(base: Base, mdp: str = MDP) -> TestClient:
    c = client_de(base)
    r = c.post("/connexion", data={"identifiant": "admin", "mot_de_passe": mdp},
               follow_redirects=False)
    assert r.status_code == 303, r.text
    return c


def creer(c: TestClient, identifiant: str = "mouabd", **entetes):
    return c.post("/comptes", data={"identifiant": identifiant, "role": "dev"}, headers=entetes,
                  follow_redirects=False)


# --- origine des POST ------------------------------------------------------------------------------
@pytest.mark.parametrize("entetes", [{"Origin": "http://attaquant.example"},
                                     {"Origin": "http://testserver:8001"},
                                     {"Origin": "null"},
                                     {"Referer": "http://attaquant.example/page"},
                                     {"Origin": "http://attaquant.example", "Referer": f"{ICI}/"}])
def test_un_post_venu_d_une_autre_origine_est_refuse(base, entetes):
    c = connecte(base)
    r = creer(c, **entetes)
    assert r.status_code == 403 and "origine" in r.text.lower()
    assert base.lire_compte("mouabd") is None
    dernier = base.journal()[-1]
    assert dernier.action == "origine_refusee" and dernier.sujet == "/comptes"


@pytest.mark.parametrize("entetes", [{"Origin": ICI}, {"Origin": "HTTP://TESTSERVER"},
                                     {"Referer": f"{ICI}/comptes"}, {}])
def test_un_post_de_la_meme_origine_passe(base, entetes):
    """Sans Origin ni Referer, ce n'est pas un navigateur : pas de CSRF possible, on laisse passer."""
    assert creer(connecte(base), **entetes).status_code == 200
    assert base.lire_compte("mouabd") is not None


def test_la_connexion_aussi_verifie_l_origine(base):
    """Une connexion forcée (login CSRF) rattacherait la victime au compte de l'attaquant."""
    c = client_de(base)
    r = c.post("/connexion", data={"identifiant": "admin", "mot_de_passe": MDP},
               headers={"Origin": "http://attaquant.example"}, follow_redirects=False)
    assert r.status_code == 403
    assert c.get("/", follow_redirects=False).headers["location"] == "/connexion"


def test_un_get_n_est_pas_concerne(base):
    c = connecte(base)
    assert c.get("/", headers={"Origin": "http://attaquant.example"}).status_code == 200


# --- un changement de mot de passe coupe les autres sessions ------------------------------------
def test_changer_son_mot_de_passe_coupe_les_autres_sessions(base):
    ici, ailleurs = connecte(base), connecte(base)
    r = ici.post("/mot-de-passe", data={"actuel": MDP, "nouveau": NOUVEAU, "confirmation": NOUVEAU},
                 follow_redirects=False)
    assert r.status_code == 303
    assert ici.get("/", follow_redirects=False).status_code == 200         # la session qui a changé
    r = ailleurs.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/connexion"
    connecte(base, NOUVEAU)                                                   # le nouveau marche


def test_une_session_sans_generation_est_coupee(base):
    """Une session ouverte avant ce correctif n'a pas de génération : elle doit se reconnecter."""
    c = client_de(base)
    app = c.app

    @app.get("/test-ancienne-session")
    def ancienne(request: module_app.Request):
        request.session.clear()
        request.session["utilisateur"] = "admin"
        return {}

    c.get("/test-ancienne-session")
    assert c.get("/", follow_redirects=False).headers["location"] == "/connexion"


# --- SAS_ADMIN_MOTDEPASSE ---------------------------------------------------------------------------
def _environnement(monkeypatch, tmp_path, mdp: str):
    monkeypatch.setenv("SAS_DB", str(tmp_path / "sas.db"))
    monkeypatch.setenv("SAS_ADMIN_MOTDEPASSE", mdp)
    monkeypatch.setenv("SAS_TRAITEMENT_INTERVALLE", "0")


def test_un_mot_de_passe_admin_trop_court_est_refuse(monkeypatch, tmp_path):
    _environnement(monkeypatch, tmp_path, "x" * (MDP_MIN - 1))
    with pytest.raises(RuntimeError, match=f"{MDP_MIN} caractères"):
        module_app._depuis_environnement()
    assert Base(str(tmp_path / "sas.db")).lister_comptes() == []


def test_un_mot_de_passe_admin_assez_long_cree_le_compte(monkeypatch, tmp_path):
    _environnement(monkeypatch, tmp_path, "x" * MDP_MIN)
    module_app._depuis_environnement()
    assert [c.identifiant for c in Base(str(tmp_path / "sas.db")).lister_comptes()] == ["admin"]


def test_la_variable_est_ignoree_une_fois_la_base_creee(monkeypatch, tmp_path):
    _environnement(monkeypatch, tmp_path, "x" * MDP_MIN)
    module_app._depuis_environnement()
    monkeypatch.setenv("SAS_ADMIN_MOTDEPASSE", "court")
    module_app._depuis_environnement()                  # la base a un compte : rien n'est refusé
