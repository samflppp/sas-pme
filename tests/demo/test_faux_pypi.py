"""Faux PyPI de démo (B) : paquet demo-horodatage (1.0 saine, 1.1 saine, 1.2 piégée), dates
contrôlées, relais vers PyPI pour le reste. Le code piégé n'est JAMAIS exécuté ici : on lit les
archives comme des données.
"""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from commun.modeles import Ecosysteme, Etat, Niveau, RapportSandbox, Version
from plateforme.db.acces import Base
from plateforme.pipeline import pypi, traitement, veille
from plateforme.pipeline.llm import ResultatLLM
from plateforme.pipeline.statique.code import controler_code

RACINE = Path(__file__).resolve().parents[2]
P = Ecosysteme.PYPI
NOM = "demo-horodatage"


def charger():
    spec = importlib.util.spec_from_file_location(
        "faux_pypi", RACINE / "demo" / "paquets" / "faux_pypi.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fp = charger()
MAINTENANT = datetime.now(timezone.utc)


@pytest.fixture
def client():
    with respx.mock(assert_all_called=False) as amont:
        amont.get("https://pypi.org/pypi/requests/json").respond(json={"info": {"name": "requests"},
                                                                       "releases": {}})
        with TestClient(fp.creer_app(amont=httpx.Client())) as c:
            yield c


def versions(client) -> dict[str, list]:
    return client.get(f"/pypi/{NOM}/json").json()["releases"]


def test_au_depart_seule_la_1_0_ancienne_est_publiee(client):
    rel = versions(client)
    assert list(rel) == ["1.0"]
    date = datetime.fromisoformat(rel["1.0"][0]["upload_time_iso_8601"].replace("Z", "+00:00"))
    assert MAINTENANT - date > timedelta(days=300)
    assert {f["filename"] for f in rel["1.0"]} == {"demo_horodatage-1.0-py3-none-any.whl",
                                                   "demo_horodatage-1.0.tar.gz"}


def test_publier_une_version_la_fait_apparaitre_maintenant_et_retirer_la_marque(client):
    assert client.post(f"/demo/publier/{NOM}/1.1").status_code == 200
    rel = versions(client)
    date = datetime.fromisoformat(rel["1.1"][0]["upload_time_iso_8601"].replace("Z", "+00:00"))
    assert abs(datetime.now(timezone.utc) - date) < timedelta(minutes=1)
    assert client.post(f"/demo/retirer/{NOM}/1.1").status_code == 200
    assert all(f["yanked"] for f in versions(client)["1.1"])
    assert client.post(f"/demo/publier/{NOM}/9.9").status_code == 404


def test_les_archives_se_telechargent_et_le_sha256_est_verifie(client, tmp_path):
    client.post(f"/demo/publier/{NOM}/1.2")
    archives = pypi.telecharger(NOM, "1.2", tmp_path, client=client, base=str(client.base_url))
    assert sorted(a.name for a in archives) == ["demo_horodatage-1.2-py3-none-any.whl",
                                                "demo_horodatage-1.2.tar.gz"]


def test_un_autre_paquet_est_relaye_vers_pypi(client):
    assert client.get("/pypi/requests/json").json()["info"]["name"] == "requests"


def test_seule_la_1_2_est_piegee_et_le_diff_le_montre(client, tmp_path):
    for v in ("1.1", "1.2"):
        client.post(f"/demo/publier/{NOM}/{v}")
    a11 = pypi.telecharger(NOM, "1.1", tmp_path / "1.1", client=client, base=str(client.base_url))
    a12 = pypi.telecharger(NOM, "1.2", tmp_path / "1.2", client=client, base=str(client.base_url))
    assert all(s.niveau.rang < Niveau.FORT.rang for s in controler_code(P, NOM, "1.1", a11))
    piege = {s.sorte: s for s in controler_code(P, NOM, "1.2", a12, precedentes=a11)}
    assert piege["exfiltration"].niveau is Niveau.BLOQUANT
    assert piege["exfiltration"].preuve["nouveau"] is True


def test_la_charge_piegee_n_envoie_qu_une_empreinte_vers_un_domaine_qui_ne_resout_jamais():
    code = fp.CODE["1.2"]
    assert ".invalid" in code and "sha256" in code
    assert "http://" not in code.replace("https://collecte.attaquant-demo.invalid", "")


def test_parcours_de_demo_de_bout_en_bout(client, tmp_path):
    """1.0 au catalogue ; la veille voit 1.1 (attend, puis publiée) ; 1.2 piégée est bloquée."""
    base = Base(str(tmp_path / "sas.db"))
    base.enregistrer_version(Version(ecosysteme=P, nom=NOM, version="1.0",
                                     publiee_le=MAINTENANT - timedelta(days=400),
                                     detectee_le=MAINTENANT, etat=Etat.PUBLIEE))
    url = str(client.base_url)
    publiees = []
    vide = RapportSandbox(requetes_dns=[], connexions=[], fichiers_sensibles=[], leurres_lus=[],
                          processus=[], code_sortie=0, duree_s=1.0, delai_depasse=False)

    def tour(quand):
        return traitement.traiter(
            base, quand, delai=timedelta(minutes=2), dossier=tmp_path / "archives",
            telecharger=lambda n, v, d: pypi.telecharger(n, v, d, client=client, base=url),
            executer=lambda *a, **k: vide,
            publier=lambda eco, n, v, archives, vid: publiees.append((n, v)),
            veiller=lambda b, m: veille.veiller(b, m, client=client, pypi_url=url,
                                                osv_url="http://osv.absent"),
            controler_meta=lambda v, prec, m: [], llm=lambda *a: ResultatLLM())

    client.post(f"/demo/publier/{NOM}/1.1")
    tour(datetime.now(timezone.utc))
    assert base.lire_version(P, NOM, "1.1").etat is Etat.EN_ATTENTE      # compte à rebours
    tour(datetime.now(timezone.utc) + timedelta(minutes=3))
    assert base.lire_version(P, NOM, "1.1").etat is Etat.PUBLIEE and publiees == [(NOM, "1.1")]
    client.post(f"/demo/publier/{NOM}/1.2")
    tour(datetime.now(timezone.utc) + timedelta(minutes=3))
    tour(datetime.now(timezone.utc) + timedelta(minutes=6))
    fiche = base.fiche(P, NOM, "1.2")
    assert fiche.version.etat is Etat.BLOQUEE and publiees == [(NOM, "1.1")]
    assert "exfiltration" in {s.sorte for s in fiche.signaux}
