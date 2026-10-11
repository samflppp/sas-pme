"""Pages « Demandes » et « Direct » (conception-demo § 1) : une demande ouvre le suivi en direct de
ses versions (le paquet et ses dépendances), étape par étape, l'IA mot à mot."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from commun.modeles import Ecosysteme, Etat, Version
from plateforme.db.acces import Base
from plateforme.web.app import creer_app
from plateforme.web.direct import Diffusion

T0 = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
MDP = "mot-de-passe-de-test"
PY = Ecosysteme.PYPI


@pytest.fixture
def base(tmp_path) -> Base:
    return Base(str(tmp_path / "sas.db"))


def faux_demander(base: Base):
    """Comme pipeline.demander : la version mûre du paquet et une dépendance, en attente."""
    def demander(eco, nom):
        principale = None
        for n, v in [(nom, "2.32.4"), ("idna", "3.10")]:
            ver = Version(ecosysteme=eco, nom=n, version=v, publiee_le=T0 - timedelta(days=5),
                          detectee_le=T0, etat=Etat.EN_ATTENTE)
            base.enregistrer_version(ver)
            principale = principale or ver
        return principale
    return demander


def client(base: Base, diffusion: Diffusion | None = None, **k) -> TestClient:
    c = TestClient(creer_app(base=base, mot_de_passe=MDP, secret="s",
                             demander=k.pop("demander", faux_demander(base)),
                             horloge=lambda: T0, delai=lambda: timedelta(days=3),
                             diffusion=diffusion or Diffusion(), duree_flux=0.3, **k))
    r = c.post("/connexion", data={"identifiant": "admin", "mot_de_passe": MDP},
               follow_redirects=False)
    assert r.status_code == 303
    return c


def demander(c: TestClient, nom="requests") -> int:
    r = c.post("/demander", data={"ecosysteme": "pypi", "nom": nom}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/direct?demande=")
    return int(r.headers["location"].split("=")[1])


def etapes(instantane: dict, nom: str) -> dict:
    v = next(x for x in instantane["versions"] if x["nom"] == nom)
    return {e["cle"]: e for e in v["etapes"]}


def test_une_demande_ouvre_le_direct_avec_le_paquet_et_ses_dependances(base):
    c = client(base)
    n = demander(c)
    entree = next(e for e in base.journal() if e.action == "demande_resolue")
    assert entree.seq == n and entree.sujet == "pypi:requests"
    assert entree.charge["versions"] == ["pypi:requests@2.32.4", "pypi:idna@3.10"]
    i = c.get(f"/direct/instantane?demande={n}").json()
    assert [v["nom"] for v in i["versions"]] == ["requests", "idna"]   # le demandé d'abord
    e = etapes(i, "requests")
    assert e["demande"]["etat"] == "fait" and "admin" in e["demande"]["detail"]
    assert e["attente"]["etat"] == "fait"            # publiée il y a 5 jours : délai écoulé
    assert e["telechargement"]["etat"] == "a_venir"


def test_une_version_trop_jeune_attend_avec_son_temps_restant(base):
    def jeune(eco, nom):
        v = Version(ecosysteme=eco, nom=nom, version="1.0", publiee_le=T0 - timedelta(days=1),
                    detectee_le=T0, etat=Etat.EN_ATTENTE)
        base.enregistrer_version(v)
        return v
    c = client(base, demander=jeune)
    e = etapes(c.get(f"/direct/instantane?demande={demander(c, 'jeune')}").json(), "jeune")
    assert e["attente"]["etat"] == "en_cours" and "2 j 00 h 00 min" in e["attente"]["detail"]


def test_les_etapes_en_memoire_avancent_et_l_ia_s_ecrit(base):
    d = Diffusion()
    c = client(base, d)
    n = demander(c)
    sujet = "pypi:requests@2.32.4"
    d.publier(sujet, "telechargement", "debut", {})
    assert etapes(c.get(f"/direct/instantane?demande={n}").json(), "requests")[
        "telechargement"]["etat"] == "en_cours"
    d.publier(sujet, "telechargement", "fin", {"archives": ["a.whl"], "duree_s": 1.5})
    d.publier(sujet, "ia", "debut", {})
    d.publier(sujet, "ia", "flux", {"explication": "Le paquet lit"})
    i = c.get(f"/direct/instantane?demande={n}").json()
    e = etapes(i, "requests")
    assert e["telechargement"]["etat"] == "fait" and e["telechargement"]["duree"] == "1,5 s"
    assert e["ia"]["etat"] == "en_cours" and e["ia"]["texte"] == "Le paquet lit"
    d.publier(sujet, "sandbox", "erreur", {"erreur": "RuntimeError: docker absent", "duree_s": 0})
    assert etapes(c.get(f"/direct/instantane?demande={n}").json(), "requests")[
        "sandbox"]["etat"] == "erreur"


def test_apres_un_redemarrage_les_etapes_se_relisent_au_journal(base):
    c = client(base)
    n = demander(c)
    sujet = "pypi:requests@2.32.4"
    base.journaliser("pipeline", "etape", sujet, {"etape": "telechargement", "etat": "fin",
                                                   "duree_s": 0.4, "archives": ["a.whl"]})
    base.journaliser("pipeline", "etape", sujet, {"etape": "politique", "etat": "fin", "duree_s": 0,
                                                   "verdict": "bloquee", "raison": "Exfiltration."})
    base.changer_etat(PY, "requests", "2.32.4", Etat.BLOQUEE, "Exfiltration.")
    i = client(base).get(f"/direct/instantane?demande={n}").json()   # une autre instance
    e = etapes(i, "requests")
    assert e["telechargement"]["etat"] == "fait"
    assert e["politique"]["etat"] == "fait" and "Exfiltration." in e["politique"]["detail"]
    v = next(x for x in i["versions"] if x["nom"] == "requests")
    assert v["etat"] == "bloquee" and v["libelle"] == "bloquée"


def test_le_flux_envoie_l_instantane_en_server_sent_events(base):
    c = client(base)
    n = demander(c)
    with c.stream("GET", f"/direct/flux?demande={n}") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        assert r.headers.get("cache-control") == "no-cache"
        corps = "".join(r.iter_text())
    donnees = [ligne[6:] for ligne in corps.splitlines() if ligne.startswith("data: ")]
    assert donnees and json.loads(donnees[0])["versions"][0]["nom"] == "requests"


def test_la_page_direct_montre_les_deux_panneaux(base):
    c = client(base)
    n = demander(c)
    t = c.get(f"/direct?demande={n}").text
    assert 'id="panneau-serveur"' in t and 'id="panneau-pipeline"' in t
    assert 'src="/statique/direct.js"' in t and f'data-demande="{n}"' in t
    assert "Téléchargement" in t and "requests" in t      # rendu sans JavaScript aussi


def test_sans_demande_direct_prend_la_derniere(base):
    c = client(base)
    demander(c, "requests")
    n2 = demander(c, "flask")
    assert f'data-demande="{n2}"' in c.get("/direct").text


def test_direct_sans_aucune_demande_invite_a_en_faire_une(base):
    t = client(base).get("/direct").text
    assert "Aucune demande" in t and 'href="/demander"' in t


def test_la_page_demandes_liste_les_demandes_recentes(base):
    c = client(base)
    n = demander(c)
    t = c.get("/demander").text
    assert f'href="/direct?demande={n}"' in t and "requests" in t and "2 versions" in t


@pytest.mark.parametrize("chemin", ["/direct?demande=999", "/direct/instantane?demande=999",
                                    "/direct/instantane?demande=1"])
def test_une_demande_inconnue_donne_404(base, chemin):
    assert client(base).get(chemin).status_code == 404     # seq 1 existe, mais n'est pas une demande


def test_il_faut_etre_connecte(base):
    c = TestClient(creer_app(base=base, mot_de_passe=MDP, secret="s", demander=lambda e, n: None))
    assert c.get("/direct/instantane?demande=1", follow_redirects=False).status_code == 303
    assert c.get("/direct/flux?demande=1", follow_redirects=False).status_code == 303


def test_une_version_deja_connue_reste_en_tete_de_sa_demande(base):
    """requests 2.32.4 déjà en base : pas re-détectée, mais c'est elle qu'on a demandée."""
    base.enregistrer_version(Version(ecosysteme=PY, nom="requests", version="2.32.4",
                                     publiee_le=T0 - timedelta(days=5), detectee_le=T0,
                                     etat=Etat.PUBLIEE))
    c = client(base)
    n = demander(c)
    assert [v["nom"] for v in c.get(f"/direct/instantane?demande={n}").json()["versions"]] == [
        "requests", "idna"]


# --- panneau Serveur : la demande part au serveur, ses requêtes se lisent à la passerelle -------
class FaussePasserelle:
    """Comme signature.demander_installation et signature.lire_acces."""

    def __init__(self):
        self.lignes, self.demandes = ["démarrage de pypiserver"], []

    def installer(self, eco, nom, demande):
        self.demandes.append((eco, nom, demande))
        return len(self.demandes)

    def requete(self, chemin, ip="10.42.2.20"):
        self.lignes.append(chemin)

    def lire(self, apres=0):
        lignes = [{"n": i, "a": f"2026-10-11 12:00:{i:02d}", "ip": "10.42.2.20", "methode": "GET",
                   "chemin": c, "code": None}
                  for i, c in enumerate(self.lignes, start=1) if i > apres and c.startswith("/")]
        return {"total": len(self.lignes), "lignes": lignes}


def test_une_demande_part_au_serveur_et_ses_requetes_s_affichent(base):
    p = FaussePasserelle()
    p.requete("/simple/vieux/")                      # avant la demande : pas affichée
    c = client(base, installer=p.installer, lire_acces=p.lire)
    n = demander(c)
    assert p.demandes == [(PY, "requests", n)]
    p.requete("/simple/requests/")
    p.requete("/packages/requests-2.32.3-py3-none-any.whl")
    s = c.get(f"/direct/instantane?demande={n}").json()["serveur"]
    assert s["configure"] and s["commande"] == "pip install requests"
    assert [x["texte"] for x in s["lignes"]] == [
        "GET /simple/requests/", "GET /packages/requests-2.32.3-py3-none-any.whl"]
    assert s["installee"] == "2.32.3"
    # la version demandée, 2.32.4, n'est pas encore publiée : le serveur a reçu la précédente
    assert s["amont"]["version"] == "2.32.4" and s["amont"]["libelle"] == "en attente"


def test_une_installation_refusee_par_la_passerelle_se_dit(base):
    def refuse(eco, nom, demande):
        raise RuntimeError("passerelle 401 : signature invalide")
    c = client(base, installer=refuse, lire_acces=FaussePasserelle().lire)
    n = demander(c)                                   # la demande, elle, aboutit
    s = c.get(f"/direct/instantane?demande={n}").json()["serveur"]
    assert "signature invalide" in s["erreur"]
    assert [e.action for e in base.journal()][-1] == "installation_echouee"


def test_sans_passerelle_le_panneau_serveur_le_dit(base):
    c = client(base)
    s = c.get(f"/direct/instantane?demande={demander(c)}").json()["serveur"]
    assert s == {"configure": False}


def test_une_demande_npm_ne_lance_pas_pip_sur_le_serveur(base):
    """L'agent de démo ne sait installer que pip : une demande npm n'est pas envoyée au serveur, et le
    panneau montre la commande npm à taper, vers le registre de la passerelle, sans fausse erreur."""
    p = FaussePasserelle()
    c = client(base, installer=p.installer, lire_acces=p.lire,
               registre_serveur="http://10.42.2.10:4873/")
    r = c.post("/demander", data={"ecosysteme": "npm", "nom": "ms"}, follow_redirects=False)
    n = int(r.headers["location"].split("=")[1])
    assert p.demandes == []
    assert "installation_echouee" not in [e.action for e in base.journal()]
    s = c.get(f"/direct/instantane?demande={n}").json()["serveur"]
    assert s["commande"] == "npm install ms" and s["erreur"] is None
    assert s["index"] == "http://10.42.2.10:4873/" and s["repli"] == "registry.npmjs.org"
    assert s["manuel"] and s["lignes"] == [] and s["amont"] is None
    page = c.get(f"/direct?demande={n}").text
    assert "npm install ms" in page and "pip install" not in page
