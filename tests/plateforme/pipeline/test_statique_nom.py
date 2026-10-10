"""Contrôle statique sur le nom (B, M1) : typosquat d'un paquet populaire."""
import pytest

from commun.modeles import Ecosysteme, Niveau, Source
from plateforme.pipeline.statique import nom as controle

POPULAIRES = {"requests", "numpy", "urllib3", "python-dateutil", "boto3", "six"}


@pytest.mark.parametrize("nom, cible", [
    ("reqeusts", "requests"),          # deux lettres inversées
    ("requestss", "requests"),         # lettre en trop
    ("nunpy", "numpy"),                # lettre remplacée
    ("Python_Dateutill", "python-dateutil"),  # casse, séparateur et lettre en trop
])
def test_typosquat_detecte(nom, cible):
    assert controle.typosquat(nom, POPULAIRES) == cible


@pytest.mark.parametrize("nom", [
    "requests",          # le paquet lui-même
    "Requests",          # le même, autre casse
    "flask",             # sans rapport
    "six7",              # nom trop court pour juger (faux positifs)
    "requests-toolbelt", # extension légitime, trop loin
])
def test_pas_de_typosquat(nom):
    assert controle.typosquat(nom, POPULAIRES) is None


def test_controler_nom_renvoie_un_signal_fort_avec_preuve():
    [s] = controle.controler_nom(Ecosysteme.PYPI, "reqeusts", "1.0", POPULAIRES)
    assert (s.source, s.niveau, s.sorte) == (Source.STATIQUE, Niveau.FORT, "typosquat")
    assert s.preuve["cible"] == "requests" and "requests" in s.preuve["extrait"]
    assert controle.controler_nom(Ecosysteme.PYPI, "flask", "3.0", POPULAIRES) == []


def test_liste_populaire_embarquee():
    populaires = controle.populaires()
    assert len(populaires) >= 1000
    assert {"requests", "numpy", "boto3"} <= populaires
