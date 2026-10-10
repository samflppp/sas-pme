from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from commun.modeles import Ecosysteme, Etat, Version
from plateforme.db.acces import Base
from plateforme.web.app import creer_app, duree_lisible

T0 = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
MDP = "mot-de-passe-de-test"


@pytest.fixture
def base(tmp_path) -> Base:
    return Base(str(tmp_path / "sas.db"))


def version(base: Base, nom: str, publiee_le: datetime, etat: Etat, raison: str = "") -> None:
    base.enregistrer_version(Version(ecosysteme=Ecosysteme.PYPI, nom=nom, version="1.0",
                                     publiee_le=publiee_le, detectee_le=publiee_le, etat=etat))
    if raison:
        base.changer_etat(Ecosysteme.PYPI, nom, "1.0", etat, raison)


def client(base: Base, maintenant: datetime, delai=lambda: timedelta(days=3)) -> TestClient:
    c = TestClient(creer_app(base=base, mot_de_passe=MDP, secret="s", demander=lambda e, n: None,
                             horloge=lambda: maintenant, delai=delai))
    r = c.post("/connexion", data={"identifiant": "admin", "mot_de_passe": MDP},
               follow_redirects=False)
    assert r.status_code == 303
    return c


@pytest.mark.parametrize("d, texte", [
    (timedelta(days=1, hours=2, minutes=41, seconds=59), "1 j 02 h 41 min"),
    (timedelta(hours=5, minutes=3), "5 h 03 min"),
    (timedelta(minutes=1, seconds=30), "1 min 30 s"),
    (timedelta(seconds=9), "9 s"),
])
def test_duree_lisible(d, texte):
    assert duree_lisible(d) == texte


def test_le_compte_a_rebours_part_de_la_publication_et_suit_le_delai(base):
    version(base, "tardif", T0 - timedelta(hours=1), Etat.EN_ATTENTE)
    version(base, "proche", T0 - timedelta(days=2), Etat.EN_ATTENTE)
    r = client(base, T0).get("/file-attente")
    assert r.status_code == 200
    assert "1 j 00 h 00 min" in r.text and "2 j 23 h 00 min" in r.text
    assert r.text.index("proche") < r.text.index("tardif")  # la fin d'attente la plus proche d'abord
    assert 'data-fin="2026-10-11T12:00:00+00:00"' in r.text  # pour le décompte en direct


def test_un_delai_de_demo_raccourcit_l_attente(base):
    version(base, "requests", T0 - timedelta(seconds=30), Etat.EN_ATTENTE)
    r = client(base, T0, delai=lambda: timedelta(seconds=120)).get("/file-attente")
    assert "1 min 30 s" in r.text and "120 s" in r.text


def test_une_attente_echue_attend_le_prochain_tour(base):
    version(base, "requests", T0 - timedelta(days=4), Etat.EN_ATTENTE)
    assert "au prochain tour" in client(base, T0).get("/file-attente").text


def test_les_versions_en_analyse_a_revoir_et_bloquees_ont_leur_section(base):
    version(base, "en-cours", T0 - timedelta(days=4), Etat.EN_ANALYSE, "analyse en cours")
    version(base, "douteux", T0 - timedelta(days=4), Etat.A_REVOIR, "À revoir : typosquat.")
    version(base, "piege", T0 - timedelta(days=4), Etat.BLOQUEE, "Bloquée : avis OpenSSF.")
    version(base, "deja-publie", T0 - timedelta(days=4), Etat.PUBLIEE, "publiée")
    t = client(base, T0).get("/file-attente").text
    assert "en-cours" in t and "douteux" in t and "À revoir : typosquat." in t
    assert "piege" in t and "Bloquée : avis OpenSSF." in t
    assert "deja-publie" not in t.split("<main>")[1]  # une version publiée n'est pas dans la file


def test_file_vide(base):
    assert "Rien en attente" in client(base, T0).get("/file-attente").text


def test_un_sas_delai_invalide_se_dit_sans_erreur_500(base):
    version(base, "requests", T0, Etat.EN_ATTENTE)

    def delai():
        raise ValueError("SAS_DELAI invalide : 'deux minutes'")
    r = client(base, T0, delai=delai).get("/file-attente")
    assert r.status_code == 200 and "SAS_DELAI invalide" in r.text


def test_la_file_est_dans_le_menu_et_demande_une_connexion(base):
    c = client(base, T0)
    assert 'href="/file-attente"' in c.get("/").text
    c.post("/deconnexion")
    assert c.get("/file-attente", follow_redirects=False).status_code == 303
