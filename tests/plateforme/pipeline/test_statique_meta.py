"""Contrôles sur les métadonnées PyPI (B, M1) : âge du projet, changement de mainteneur."""
from datetime import datetime, timedelta, timezone

import httpx
import respx

from commun.modeles import Ecosysteme, Niveau
from plateforme.pipeline.statique import meta

PYPI = "https://pypi.test"
MAINTENANT = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
P = Ecosysteme.PYPI


def projet(premier_il_y_a_j: int) -> dict:
    def f(j):
        return [{"upload_time_iso_8601": (MAINTENANT - timedelta(days=j)).isoformat()}]
    return {"info": {}, "releases": {"0.1": f(premier_il_y_a_j), "1.0": f(1)}}


def version_json(courriel: str, auteur: str = "Ana") -> dict:
    return {"info": {"author": auteur, "author_email": courriel, "maintainer": None,
                     "maintainer_email": ""}}


def lancer(precedente=None):
    with httpx.Client() as client:
        return meta.controler_metadonnees(P, "demo", "1.0", precedente=precedente,
                                          maintenant=MAINTENANT, client=client, base_url=PYPI)


@respx.mock
def test_un_projet_ancien_au_meme_mainteneur_ne_donne_rien():
    respx.get(f"{PYPI}/pypi/demo/json").respond(json=projet(400))
    respx.get(f"{PYPI}/pypi/demo/1.0/json").respond(json=version_json("ana@exemple.org"))
    respx.get(f"{PYPI}/pypi/demo/0.1/json").respond(json=version_json("Ana@Exemple.org"))
    assert lancer("0.1") == []


@respx.mock
def test_un_projet_de_moins_de_30_jours_est_signale():
    respx.get(f"{PYPI}/pypi/demo/json").respond(json=projet(10))
    [s] = lancer()
    assert (s.sorte, s.niveau) == ("projet_recent", Niveau.MOYEN)
    assert "10 jours" in s.preuve["extrait"]


@respx.mock
def test_un_nouveau_mainteneur_depuis_la_version_precedente_est_signale():
    respx.get(f"{PYPI}/pypi/demo/json").respond(json=projet(400))
    respx.get(f"{PYPI}/pypi/demo/1.0/json").respond(json=version_json("x@proton.example"))
    respx.get(f"{PYPI}/pypi/demo/0.1/json").respond(json=version_json("ana@exemple.org"))
    [s] = lancer("0.1")
    assert (s.sorte, s.niveau) == ("mainteneur_change", Niveau.MOYEN)
    assert "x@proton.example" in s.preuve["extrait"] and s.preuve["precedente"] == "0.1"


@respx.mock
def test_pypi_injoignable_ne_donne_aucun_signal_et_ne_plante_pas():
    respx.get(f"{PYPI}/pypi/demo/json").mock(side_effect=httpx.ConnectError("hors ligne"))
    assert lancer("0.1") == []
