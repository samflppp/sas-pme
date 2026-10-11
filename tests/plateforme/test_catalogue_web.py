"""Catalogue en arborescence (conception-demo § 1) : écosystèmes, paquets, versions et fichiers, à la
manière d'un dépôt GitHub ; les images Docker tenues à la main, dites comme telles."""
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from commun.modeles import Ecosysteme, Etat, Niveau, RapportSandbox, Signal, Source, Verdict, Version
from plateforme.db.acces import Base
from plateforme.web.app import creer_app
from plateforme.web.catalogue import paquet

T0 = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
MDP = "mot-de-passe-de-test"
PY, NPM = Ecosysteme.PYPI, Ecosysteme.NPM


@pytest.fixture
def base(tmp_path) -> Base:
    return Base(str(tmp_path / "sas.db"))


def ajouter(base: Base, nom: str, v: str, etat: Etat, jours: float = 10, eco=PY,
            raison: str = "pour le test") -> Version:
    ver = Version(ecosysteme=eco, nom=nom, version=v, publiee_le=T0 - timedelta(days=jours),
                  detectee_le=T0 - timedelta(days=jours), etat=Etat.EN_ATTENTE)
    base.enregistrer_version(ver)
    if etat is not Etat.EN_ATTENTE:
        base.changer_etat(eco, nom, v, etat, raison)
    return ver


@pytest.fixture
def images(tmp_path):
    chemin = tmp_path / "images.json"
    chemin.write_text(json.dumps([{
        "nom": "python", "tag": "3.12-slim", "source": "docker.io/library/python",
        "digest": "sha256:" + "a" * 64, "agreee_le": "2026-10-11", "par": "admin",
        "usage": "image de base des services Python"}]), encoding="utf-8")
    return chemin


def connecte(base: Base, tmp_path, images=None) -> TestClient:
    c = TestClient(creer_app(base=base, mot_de_passe=MDP, secret="s", demander=lambda e, n: None,
                             horloge=lambda: T0, delai=lambda: timedelta(days=3),
                             archives=tmp_path / "archives", images=images))
    r = c.post("/connexion", data={"identifiant": "admin", "mot_de_passe": MDP},
               follow_redirects=False)
    assert r.status_code == 303
    return c


# --- le paquet : version servie, version qui attend ------------------------------------------
def test_la_version_servie_est_la_plus_recente_publiee_au_sens_pep440(base):
    for v, etat in [("2.9", Etat.PUBLIEE), ("2.10", Etat.PUBLIEE), ("2.11", Etat.EN_ATTENTE),
                    ("2.8", Etat.REVOQUEE)]:
        ajouter(base, "requests", v, etat)
    p = paquet(base.lister_versions(), PY, "requests")
    assert p.servie.version == "2.10"            # « 2.10 » > « 2.9 », pas l'ordre des chaînes
    assert p.suivante.version == "2.11"          # plus récente que la servie, pas encore publiée
    assert [v.version for v in p.versions] == ["2.11", "2.10", "2.9", "2.8"]


def test_rien_de_plus_recent_que_la_servie_pas_de_suivante(base):
    ajouter(base, "idna", "3.20", Etat.PUBLIEE)
    ajouter(base, "idna", "3.19", Etat.BLOQUEE)
    p = paquet(base.lister_versions(), PY, "idna")
    assert p.servie.version == "3.20" and p.suivante is None


# --- les pages --------------------------------------------------------------------------------
def test_la_racine_montre_les_trois_dossiers_et_leurs_comptes(base, tmp_path, images):
    ajouter(base, "requests", "2.32.4", Etat.PUBLIEE)
    ajouter(base, "idna", "3.20", Etat.PUBLIEE)
    ajouter(base, "left-pad", "1.3.0", Etat.PUBLIEE, eco=NPM)
    t = connecte(base, tmp_path, images).get("/").text
    assert 'href="/catalogue/pypi"' in t and 'href="/catalogue/npm"' in t
    assert 'href="/catalogue/images"' in t
    assert "2 paquets" in t and "1 paquet" in t and "1 image" in t


def test_un_ecosysteme_liste_ses_paquets(base, tmp_path):
    ajouter(base, "requests", "2.32.4", Etat.PUBLIEE)
    ajouter(base, "left-pad", "1.3.0", Etat.PUBLIEE, eco=NPM)
    t = connecte(base, tmp_path).get("/catalogue/pypi").text
    assert 'href="/catalogue/pypi/requests"' in t and "left-pad" not in t


def test_le_paquet_dit_ce_que_recoivent_les_serveurs_et_ce_qui_attend(base, tmp_path):
    ajouter(base, "requests", "2.32.4", Etat.PUBLIEE, jours=40)
    ajouter(base, "requests", "2.33.1", Etat.EN_ATTENTE, jours=1)
    t = connecte(base, tmp_path).get("/catalogue/pypi/requests").text
    assert t.index("2.33.1") < t.index("2.32.4")                    # la plus récente en tête
    assert 'href="/catalogue/pypi/requests/-/2.32.4"' in t
    assert "Les serveurs reçoivent <strong>2.32.4</strong>" in t
    assert "2.33.1" in t and "encore 2 j 00 h 00 min" in t         # 3 jours - 1 jour écoulé


def test_la_version_liste_ses_archives_et_ses_donnees(base, tmp_path):
    ajouter(base, "requests", "2.32.4", Etat.PUBLIEE)
    dossier = tmp_path / "archives" / "requests" / "2.32.4"
    dossier.mkdir(parents=True)
    contenu = b"faux wheel" * 200
    (dossier / "requests-2.32.4-py3-none-any.whl").write_bytes(contenu)
    base.enregistrer_verdict(PY, "requests", "2.32.4", Verdict(
        etat=Etat.APPROUVEE, raison="Aucun signal.", signaux=[], explication_llm="Rien à signaler."))
    t = connecte(base, tmp_path).get("/catalogue/pypi/requests/-/2.32.4").text
    assert "requests-2.32.4-py3-none-any.whl" in t
    assert hashlib.sha256(contenu).hexdigest()[:12] in t and "2,0 Ko" in t
    assert 'href="/catalogue/pypi/requests/-/2.32.4/verdict.json"' in t
    assert 'href="/versions/pypi/requests/2.32.4"' in t              # la fiche complète


def test_un_fichier_de_donnees_s_affiche_comme_sur_github(base, tmp_path):
    ajouter(base, "demo-horodatage", "1.2", Etat.BLOQUEE)
    base.enregistrer_rapport_sandbox(PY, "demo-horodatage", "1.2", RapportSandbox(
        requetes_dns=["exfil.demo.invalid"], connexions=[], fichiers_sensibles=["~/.aws/credentials"],
        leurres_lus=[], processus=[], code_sortie=0, duree_s=4.2, delai_depasse=False))
    base.ajouter_signal(Signal(ecosysteme=PY, nom="demo-horodatage", version="1.2",
                               source=Source.SANDBOX, niveau=Niveau.BLOQUANT, sorte="exfiltration",
                               preuve={"domaine": "exfil.demo.invalid"}))
    c = connecte(base, tmp_path)
    t = c.get("/catalogue/pypi/demo-horodatage/-/1.2/rapport-sandbox.json").text
    assert "exfil.demo.invalid" in t and 'class="blob"' in t
    assert "exfiltration" in c.get("/catalogue/pypi/demo-horodatage/-/1.2/signaux.json").text
    assert c.get("/catalogue/pypi/demo-horodatage/-/1.2/verdict.json").status_code == 404
    assert c.get("/catalogue/pypi/demo-horodatage/-/1.2/autre.json").status_code == 404


def test_un_nom_npm_a_portee_se_parcourt(base, tmp_path):
    ajouter(base, "@types/node", "22.1.0", Etat.PUBLIEE, eco=NPM)
    c = connecte(base, tmp_path)
    assert 'href="/catalogue/npm/@types/node"' in c.get("/catalogue/npm").text
    assert 'href="/catalogue/npm/@types/node/-/22.1.0"' in c.get("/catalogue/npm/@types/node").text
    assert c.get("/catalogue/npm/@types/node/-/22.1.0").status_code == 200


@pytest.mark.parametrize("chemin", [
    "/catalogue/pip", "/catalogue/pypi/inconnu", "/catalogue/pypi/requests/-/9.9",
    "/catalogue/pypi/requests/-/2.32.4/../../../sas.db", "/catalogue/pypi/..%2F..%2Fsas.db",
])
def test_un_chemin_inconnu_donne_404(base, tmp_path, chemin):
    ajouter(base, "requests", "2.32.4", Etat.PUBLIEE)
    assert connecte(base, tmp_path).get(chemin).status_code == 404


def test_les_images_sont_dites_ajoutees_a_la_main(base, tmp_path, images):
    t = connecte(base, tmp_path, images).get("/catalogue/images").text
    assert "python" in t and "3.12-slim" in t and "sha256:aaaaaaaaaaaa" in t
    assert "ajoutées à la main" in t and "non analysées par la pipeline" in t


def test_sans_fichier_d_images_le_dossier_est_vide(base, tmp_path):
    t = connecte(base, tmp_path, tmp_path / "absent.json").get("/catalogue/images").text
    assert "Aucune image" in t


def test_le_fil_d_ariane_mene_a_chaque_dossier(base, tmp_path):
    ajouter(base, "requests", "2.32.4", Etat.PUBLIEE)
    t = connecte(base, tmp_path).get("/catalogue/pypi/requests/-/2.32.4").text
    fil = t[t.index('class="depot-fil"'):t.index("</nav>", t.index('class="depot-fil"'))]
    assert 'href="/"' in fil and 'href="/catalogue/pypi"' in fil
    assert 'href="/catalogue/pypi/requests"' in fil and "<strong>2.32.4</strong>" in fil
