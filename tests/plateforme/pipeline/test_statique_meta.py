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


# --- npm : âge du projet (time.created) et éditeur de la version (_npmUser) ------------------
NPM = "https://npm.test"


def paquet_npm(cree_il_y_a: int, editeurs: dict[str, str]) -> dict:
    return {"name": "demo", "time": {"created": (MAINTENANT - timedelta(days=cree_il_y_a))
                                     .isoformat().replace("+00:00", "Z")},
            "versions": {v: {"version": v, "_npmUser": {"name": e.split("@")[0], "email": e}}
                         for v, e in editeurs.items()}}


def lancer_npm(paquet, precedente="1.0.0"):
    with respx.mock:
        respx.get(f"{NPM}/demo").respond(json=paquet)
        with httpx.Client() as c:
            return meta.controler_metadonnees(Ecosysteme.NPM, "demo", "1.1.0", precedente=precedente,
                                              maintenant=MAINTENANT, client=c, npm_url=NPM)


def test_npm_un_editeur_different_de_la_version_precedente_est_signale():
    s = lancer_npm(paquet_npm(400, {"1.0.0": "alice@ex.org", "1.1.0": "mallory@evil.test"}))
    assert [(x.sorte, x.niveau) for x in s] == [("mainteneur_change", Niveau.MOYEN)]
    assert "mallory@evil.test" in s[0].preuve["extrait"]


def test_npm_un_projet_recent_est_signale_et_le_meme_editeur_ne_l_est_pas():
    s = lancer_npm(paquet_npm(5, {"1.0.0": "alice@ex.org", "1.1.0": "alice@ex.org"}))
    assert [x.sorte for x in s] == ["projet_recent"]
