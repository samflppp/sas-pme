"""Politique factice M0 : tout approuver (remplacée en M1 par la politique déterministe)."""
from commun.modeles import Ecosysteme, Etat, Niveau, Signal, Source, Verdict
from plateforme.pipeline import politique


def test_politique_factice_approuve_et_garde_les_signaux():
    s = Signal(ecosysteme=Ecosysteme.PYPI, nom="demo", version="1.1", source=Source.STATIQUE,
               niveau=Niveau.INFO, sorte="age")
    v = politique.decider([s])
    assert isinstance(v, Verdict)
    assert v.etat is Etat.APPROUVEE
    assert v.signaux == [s]
    assert "factice" in v.raison
