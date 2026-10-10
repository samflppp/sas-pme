import threading
import time

from fastapi.testclient import TestClient

from plateforme.db.acces import Base
from plateforme.web.app import creer_app
from plateforme.web.fond import TacheDeFond


def attendre(condition, delai=2.0) -> bool:
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if condition():
            return True
        time.sleep(0.005)
    return False


def test_la_tache_est_appelee_en_boucle_sans_jamais_se_chevaucher():
    appels, en_cours, maximum = [], [0], [0]
    verrou = threading.Lock()

    def lente():
        with verrou:
            en_cours[0] += 1
            maximum[0] = max(maximum[0], en_cours[0])
        time.sleep(0.02)  # plus long que l'intervalle
        appels.append(1)
        with verrou:
            en_cours[0] -= 1

    tache = TacheDeFond(lente, intervalle=0.001)
    tache.demarrer()
    assert attendre(lambda: len(appels) >= 3)
    tache.arreter()
    assert maximum[0] == 1


def test_une_erreur_n_arrete_pas_la_boucle(capsys):
    appels = []

    def fragile():
        appels.append(1)
        if len(appels) == 1:
            raise RuntimeError("passerelle injoignable")

    tache = TacheDeFond(fragile, intervalle=0.001)
    tache.demarrer()
    assert attendre(lambda: len(appels) >= 2)
    tache.arreter()
    assert "passerelle injoignable" in capsys.readouterr().err


def test_arreter_n_attend_pas_la_fin_de_l_intervalle():
    tache = TacheDeFond(lambda: None, intervalle=60)
    tache.demarrer()
    debut = time.monotonic()
    tache.arreter()
    assert time.monotonic() - debut < 1
    assert not tache.vivante()


def test_l_application_lance_traiter_avec_sa_base_et_l_arrete_a_la_fermeture(tmp_path):
    base = Base(str(tmp_path / "sas.db"))
    recues = []
    app = creer_app(base=base, mot_de_passe="m", secret="s", demander=lambda e, n: None,
                    traiter=recues.append, intervalle=0.001)
    with TestClient(app):
        assert attendre(lambda: len(recues) >= 2)
    assert all(b is base for b in recues)
    n = len(recues)
    time.sleep(0.05)
    assert len(recues) == n  # plus rien après la fermeture


def test_sans_traiter_aucune_tache_de_fond(tmp_path):
    app = creer_app(base=Base(str(tmp_path / "sas.db")), mot_de_passe="m", secret="s",
                    demander=lambda e, n: None)
    with TestClient(app) as client:
        assert client.get("/sante").json() == {"ok": True}
