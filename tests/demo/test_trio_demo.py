"""Le trio de démo (enregistrement vidéo) : pour PyPI et pour npm, un paquet qui passe (vert), un à
revoir (orange) et un bloqué (rouge), servis par les fausses sources amont, déjà mûrs (publiés il y a
400 jours : aucun délai à attendre). Chaque verdict vient de la vraie analyse statique et de la
vraie politique ; la sandbox et le LLM sont neutres ici, ils ne font qu'ajouter des preuves."""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from commun.modeles import Ecosysteme, Etat, RapportSandbox, Version
from plateforme.db.acces import Base
from plateforme.pipeline import npm, pypi, traitement
from plateforme.pipeline.llm import ResultatLLM

RACINE = Path(__file__).resolve().parents[2]
MAINTENANT = datetime.now(timezone.utc)
VIDE = RapportSandbox(requetes_dns=[], connexions=[], fichiers_sensibles=[], leurres_lus=[],
                      processus=[], code_sortie=0, duree_s=1.0, delai_depasse=False)
ATTENDU = {"sain": Etat.PUBLIEE, "a-revoir": Etat.A_REVOIR, "piege": Etat.BLOQUEE}


def charger(nom: str):
    spec = importlib.util.spec_from_file_location(nom, RACINE / "demo" / "paquets" / f"{nom}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def faux_pypi():
    with respx.mock(assert_all_called=False):
        with TestClient(charger("faux_pypi").creer_app(amont=httpx.Client())) as c:
            yield c


@pytest.fixture
def faux_npm():
    with respx.mock(assert_all_called=False) as amont:
        amont.get("https://registry.npmjs.org/ms").respond(json={"name": "ms", "versions": {}})
        with TestClient(charger("faux_npm").creer_app(amont=httpx.Client())) as c:
            yield c


def analyser(tmp_path, eco: Ecosysteme, nom: str, version: str, telecharger) -> Etat:
    base = Base(str(tmp_path / "sas.db"))
    base.enregistrer_version(Version(ecosysteme=eco, nom=nom, version=version,
                                     publiee_le=MAINTENANT - timedelta(days=400),
                                     detectee_le=MAINTENANT, etat=Etat.EN_ATTENTE))
    traitement.traiter(base, MAINTENANT, delai=timedelta(minutes=2), dossier=tmp_path / "a",
                       telecharger=telecharger, executer=lambda *a, **k: VIDE,
                       publier=lambda *a: None, veiller=lambda b, m: None,
                       controler_meta=lambda v, p, m: [], llm=lambda *a: ResultatLLM())
    return base.lire_version(eco, nom, version).etat


@pytest.mark.parametrize("sorte", ATTENDU)
def test_pypi_un_vert_un_orange_un_rouge(faux_pypi, tmp_path, sorte):
    nom, url = f"demo-{sorte}", str(faux_pypi.base_url)
    mure = pypi.derniere_version_mure(nom, MAINTENANT, client=faux_pypi, base=url)
    assert mure is not None and mure[0] == "1.0"                 # déjà mûre : rien à attendre
    etat = analyser(tmp_path, Ecosysteme.PYPI, nom, "1.0",
                    lambda n, v, d: pypi.telecharger(n, v, d, client=faux_pypi, base=url))
    assert etat is ATTENDU[sorte]


@pytest.mark.parametrize("sorte", ATTENDU)
def test_npm_un_vert_un_orange_un_rouge(faux_npm, tmp_path, sorte):
    nom, url = f"demo-npm-{sorte}", str(faux_npm.base_url).rstrip("/")
    mure = npm.derniere_version_mure(nom, MAINTENANT, client=faux_npm, base=url)
    assert mure is not None and mure[0] == "1.0.0"
    assert npm.dependances(nom, "1.0.0", client=faux_npm, base=url) == {}
    etat = analyser(tmp_path, Ecosysteme.NPM, nom, "1.0.0",
                    lambda n, v, d: npm.telecharger(n, v, d, client=faux_npm, base=url))
    assert etat is ATTENDU[sorte]


def test_le_faux_npm_relaie_les_autres_paquets_vers_npmjs(faux_npm):
    assert faux_npm.get("/ms").json()["name"] == "ms"


def test_les_charges_piegees_ne_visent_qu_un_domaine_qui_ne_resout_jamais():
    fn = charger("faux_npm")
    assert "collecte.attaquant-demo.invalid" in fn.FICHIERS["demo-npm-piege"]["post.js"]
    for fichiers in fn.FICHIERS.values():                       # aucun autre domaine joignable
        for texte in fichiers.values():
            for hote in ("http://", "https://"):
                for morceau in texte.split(hote)[1:]:
                    domaine = morceau.split("/")[0].split('"')[0].split("'")[0]
                    assert domaine.endswith((".invalid", ".ngrok-free.app")), domaine
