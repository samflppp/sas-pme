"""Page « Inventaire » (M2, contrat § 4) : ce que les serveurs ont réellement installé, croisé avec
l'état de chaque version sur la plateforme."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from commun.modeles import Ecosysteme, EntreeInventaire, Etat, Version
from plateforme.db.acces import Base
from plateforme.web.app import creer_app, croiser

T0 = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
MDP = "mot-de-passe-de-test"
PY = Ecosysteme.PYPI


@pytest.fixture
def base(tmp_path) -> Base:
    return Base(str(tmp_path / "sas.db"))


def entree(nom: str, version: str, n: int = 0) -> EntreeInventaire:
    return EntreeInventaire(ecosysteme=PY, nom=nom, version=version, telechargements=n,
                            dernier=T0 if n else None)


def version(nom: str, v: str, etat: Etat) -> Version:
    return Version(ecosysteme=PY, nom=nom, version=v, publiee_le=T0, detectee_le=T0, etat=etat)


def enregistrer(base: Base, nom: str, v: str, etat: Etat) -> None:
    base.enregistrer_version(version(nom, v, Etat.EN_ATTENTE))
    base.changer_etat(PY, nom, v, etat, "pour le test")


def connecte(base: Base, lire) -> TestClient:
    c = TestClient(creer_app(base=base, mot_de_passe=MDP, secret="s", demander=lambda e, n: None,
                             lire_inventaire=lire))
    r = c.post("/connexion", data={"identifiant": "admin", "mot_de_passe": MDP},
               follow_redirects=False)
    assert r.status_code == 303
    return c


# --- croiser -----------------------------------------------------------------------------------
def test_les_noms_et_les_versions_sont_compares_normalises():
    """Le dépôt écrit « Demo_Horodatage 1.10.0 », la plateforme « demo-horodatage 1.10 »."""
    (ligne,) = croiser([entree("Demo_Horodatage", "1.10.0", 2)],
                       [version("demo-horodatage", "1.10", Etat.PUBLIEE)])
    assert ligne.version is not None and ligne.version.version == "1.10"
    assert ligne.alerte is None


@pytest.mark.parametrize("etat, n, attendu", [
    (Etat.REVOQUEE, 3, "Révoquée depuis, et téléchargée 3 fois"),
    (Etat.BLOQUEE, 1, "Bloquée depuis, et téléchargée 1 fois"),
    (Etat.REVOQUEE, 0, "Révoquée depuis, mais encore sur le dépôt"),
    (Etat.APPROUVEE, 0, "« approuvee » sur la plateforme"),
    (Etat.A_REVOIR, 2, "« a_revoir » sur la plateforme"),
])
def test_une_version_installee_mais_pas_publiee_est_une_alerte(etat, n, attendu):
    (ligne,) = croiser([entree("demo", "1.2", n)], [version("demo", "1.2", etat)])
    assert attendu in ligne.alerte


def test_une_version_inconnue_de_la_plateforme_est_une_alerte():
    (ligne,) = croiser([entree("pirate", "6.6.6", 4)], [version("demo", "1.2", Etat.PUBLIEE)])
    assert ligne.version is None and "Inconnue de la plateforme" in ligne.alerte


def test_une_version_publiee_n_est_pas_une_alerte():
    (ligne,) = croiser([entree("demo", "1.1", 9)], [version("demo", "1.1", Etat.PUBLIEE)])
    assert ligne.alerte is None


def test_les_alertes_viennent_d_abord():
    lignes = croiser([entree("a", "1.0", 1), entree("b", "1.0", 1), entree("c", "1.0", 1)],
                     [version("a", "1.0", Etat.PUBLIEE), version("b", "1.0", Etat.REVOQUEE),
                      version("c", "1.0", Etat.PUBLIEE)])
    assert [(l.entree.nom, l.alerte is not None) for l in lignes] == \
        [("b", True), ("a", False), ("c", False)]


def test_une_version_illisible_ne_casse_rien():
    (ligne,) = croiser([entree("demo", "pas une version")],
                       [version("demo", "pas une version", Etat.PUBLIEE)])
    assert ligne.alerte is None


# --- la page -----------------------------------------------------------------------------------
def test_la_page_croise_l_inventaire_et_garde_l_instantane(base):
    enregistrer(base, "demo-horodatage", "1.1", Etat.PUBLIEE)
    enregistrer(base, "demo-horodatage", "1.2", Etat.REVOQUEE)
    entrees = [entree("demo_horodatage", "1.1", 5), entree("demo_horodatage", "1.2", 2)]
    t = connecte(base, lambda: entrees).get("/inventaire")
    assert t.status_code == 200
    assert 'data-alertes="1"' in t.text
    assert "Révoquée depuis, et téléchargée 2 fois" in t.text
    assert 'href="/versions/pypi/demo-horodatage/1.2"' in t.text     # la fiche de la plateforme
    assert base.inventaire() == [(PY, "demo_horodatage", "1.1"), (PY, "demo_horodatage", "1.2")]


def test_une_passerelle_injoignable_le_dit_sans_toucher_l_instantane(base):
    base.enregistrer_inventaire([entree("demo", "1.0", 1)])

    def panne():
        raise OSError("connexion refusée")

    r = connecte(base, panne).get("/inventaire")
    assert r.status_code == 502 and "connexion refusée" in r.text
    assert base.inventaire() == [(PY, "demo", "1.0")]


def test_un_inventaire_vide(base):
    t = connecte(base, lambda: []).get("/inventaire").text
    assert 'data-alertes="0"' in t and "Aucune version installée" in t


def test_il_faut_etre_connecte(base):
    c = TestClient(creer_app(base=base, mot_de_passe=MDP, secret="s", demander=lambda e, n: None,
                             lire_inventaire=lambda: []))
    r = c.get("/inventaire", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/connexion"


def test_le_lien_est_dans_la_navigation(base):
    assert 'href="/inventaire"' in connecte(base, lambda: []).get("/").text


def test_un_nom_venu_de_la_passerelle_ne_s_execute_pas(base):
    t = connecte(base, lambda: [entree("<script>x</script>", "1.0")]).get("/inventaire").text
    assert "<script>x</script>" not in t and "&lt;script&gt;" in t
