"""Politique : le code décide. Un signal FORT met à revoir, un signal BLOQUANT bloque."""
import pytest

from commun.modeles import Ecosysteme, Etat, Niveau, Signal, Source, Verdict
from plateforme.pipeline import politique


def signal(niveau: Niveau, sorte: str = "age", extrait: str | None = None) -> Signal:
    return Signal(ecosysteme=Ecosysteme.PYPI, nom="demo", version="1.1", source=Source.STATIQUE,
                  niveau=niveau, sorte=sorte, preuve={"extrait": extrait} if extrait else {})


@pytest.mark.parametrize("signaux", [[], [signal(Niveau.INFO)], [signal(Niveau.MOYEN)]])
def test_sans_signal_fort_la_version_est_approuvee(signaux):
    v = politique.decider(signaux)
    assert isinstance(v, Verdict)
    assert v.etat is Etat.APPROUVEE
    assert v.signaux == signaux


def test_un_signal_fort_met_a_revoir_et_donne_sa_preuve():
    s = signal(Niveau.FORT, "typosquat", "« reqeusts » imite « requests »")
    v = politique.decider([signal(Niveau.INFO), s])
    assert v.etat is Etat.A_REVOIR
    assert "reqeusts" in v.raison


def test_un_signal_bloquant_bloque_meme_avec_un_fort():
    v = politique.decider([signal(Niveau.FORT, "typosquat"), signal(Niveau.BLOQUANT, "lit_leurre")])
    assert v.etat is Etat.BLOQUEE
    assert "lit_leurre" in v.raison
