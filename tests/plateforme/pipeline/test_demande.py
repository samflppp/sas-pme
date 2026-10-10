"""pipeline.demander (B, M0) : choisit la dernière version mûre et l'enregistre en attente."""
from datetime import datetime, timedelta, timezone

import pytest

from commun.modeles import Ecosysteme, Etat, Version
from plateforme import pipeline

MAINTENANT = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
PUBLIEE = MAINTENANT - timedelta(days=5)


def faux_choix(nom, maintenant, **_):
    return {"demo": ("1.1", PUBLIEE)}.get(nom)


def test_demander_enregistre_la_derniere_version_mure(monkeypatch):
    monkeypatch.setattr(pipeline.pypi, "derniere_version_mure", faux_choix)
    enregistrees: list[Version] = []
    v = pipeline.demander(Ecosysteme.PYPI, "demo", maintenant=MAINTENANT,
                          enregistrer=lambda x: enregistrees.append(x) or True)
    assert enregistrees == [v]
    assert (v.ecosysteme, v.nom, v.version, v.etat) == (Ecosysteme.PYPI, "demo", "1.1",
                                                        Etat.EN_ATTENTE)
    assert v.publiee_le == PUBLIEE and v.detectee_le == MAINTENANT


def test_demander_sans_version_mure_leve_lookuperror(monkeypatch):
    monkeypatch.setattr(pipeline.pypi, "derniere_version_mure", faux_choix)
    with pytest.raises(LookupError):
        pipeline.demander(Ecosysteme.PYPI, "absent", maintenant=MAINTENANT,
                          enregistrer=lambda x: pytest.fail("rien ne doit être enregistré"))


def test_demander_npm_hors_mvp():
    with pytest.raises(NotImplementedError):
        pipeline.demander(Ecosysteme.NPM, "left-pad", maintenant=MAINTENANT,
                          enregistrer=lambda x: True)
