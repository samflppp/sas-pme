"""Gabarit de la plateforme (conception-demo § 1) : barre latérale, styles et polices servis par la
plateforme elle-même, aucune ressource extérieure."""
import re

import pytest
from fastapi.testclient import TestClient

from plateforme.db.acces import Base
from plateforme.web.app import creer_app

MDP = "mot-de-passe-de-test"


@pytest.fixture
def client(tmp_path) -> TestClient:
    base = Base(str(tmp_path / "sas.db"))
    c = TestClient(creer_app(base=base, mot_de_passe=MDP, secret="s", demander=lambda e, n: None,
                             lire_inventaire=lambda: []))
    r = c.post("/connexion", data={"identifiant": "admin", "mot_de_passe": MDP},
               follow_redirects=False)
    assert r.status_code == 303
    return c


def test_la_feuille_de_style_et_les_polices_sont_servies(client):
    css = client.get("/statique/plateforme.css")
    assert css.status_code == 200 and css.headers["content-type"].startswith("text/css")
    polices = re.findall(r'url\("(polices/[^"]+)"\)', css.text)
    assert polices, "la feuille déclare ses polices"
    for p in polices:
        r = client.get(f"/statique/{p}")
        assert r.status_code == 200 and len(r.content) > 1000, p


def test_aucune_ressource_exterieure(client):
    for chemin in ("/", "/tableau-de-bord", "/inventaire", "/connexion"):
        t = client.get(chemin).text
        externes = re.findall(r'<(?:link|script|img)[^>]+(?:href|src)="(https?:)?//', t)
        assert not externes, chemin
        assert 'href="/statique/plateforme.css"' in t, chemin


def test_la_barre_laterale_marque_la_page_en_cours(client):
    t = client.get("/inventaire").text
    nav = re.search(r'<nav class="laterale".*?</nav>', t, re.S)
    assert nav, "la barre latérale est là"
    courants = re.findall(r'<a href="([^"]+)" aria-current="page"', nav.group(0))
    assert courants == ["/inventaire"]


def test_la_page_de_connexion_n_a_pas_de_barre_laterale(tmp_path):
    base = Base(str(tmp_path / "sas.db"))
    c = TestClient(creer_app(base=base, mot_de_passe=MDP, secret="s", demander=lambda e, n: None))
    t = c.get("/connexion").text
    assert 'class="laterale"' not in t and 'href="/statique/plateforme.css"' in t


def test_les_etats_s_affichent_en_francais_lisible(client):
    """La pastille garde l'état en classe (couleur), mais dit « en attente », pas « en_attente »."""
    t = client.get("/tableau-de-bord").text
    pastilles = dict(re.findall(r'<span class="etat etat-([a-z_]+)">([^<]+)</span>', t))
    assert pastilles["en_attente"] == "en attente" and pastilles["a_revoir"] == "à revoir"
    assert pastilles["publiee"] == "publiée" and pastilles["revoquee"] == "révoquée"
