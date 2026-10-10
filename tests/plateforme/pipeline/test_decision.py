"""pipeline.decision_humaine (B, contrat § 5) : un admin tranche une version « à revoir »."""
from datetime import datetime, timedelta, timezone

import pytest

from commun.modeles import Ecosysteme, Etat, Niveau, Signal, Source, Version
from plateforme import pipeline
from plateforme.db.acces import Base
from plateforme.pipeline import politique

P = Ecosysteme.PYPI
MAINTENANT = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)


def signal(niveau: Niveau, source: Source = Source.STATIQUE, sorte: str = "typosquat") -> Signal:
    return Signal(ecosysteme=P, nom="reqeusts", version="1.0", source=source, niveau=niveau,
                  sorte=sorte, preuve={"extrait": "« reqeusts » imite « requests »"})


@pytest.fixture
def base(tmp_path):
    b = Base(str(tmp_path / "sas.db"))
    b.enregistrer_version(Version(ecosysteme=P, nom="reqeusts", version="1.0",
                                  publiee_le=MAINTENANT - timedelta(days=5),
                                  detectee_le=MAINTENANT, etat=Etat.EN_ATTENTE))
    s = signal(Niveau.FORT)
    b.ajouter_signal(s)
    v = politique.decider([s])
    b.enregistrer_verdict(P, "reqeusts", "1.0", v)
    b.changer_etat(P, "reqeusts", "1.0", v.etat, v.raison)
    return b


def test_un_admin_approuve_une_version_a_revoir(base):
    v = pipeline.decision_humaine(base, P, "reqeusts", "1.0", Etat.APPROUVEE,
                                  "nom interne connu, vérifié avec l'équipe", acteur="alice")
    assert v.etat is Etat.APPROUVEE
    fiche = base.fiche(P, "reqeusts", "1.0")
    assert fiche.version.etat is Etat.APPROUVEE and fiche.verdict.etat is Etat.APPROUVEE
    humain = [s for s in fiche.signaux if s.source is Source.HUMAIN]
    assert [(s.sorte, s.preuve["acteur"]) for s in humain] == [("approbation_humaine", "alice")]
    assert "alice" in fiche.raison and "vérifié avec l'équipe" in fiche.raison
    assert base.journal()[-1].acteur == "alice"
    assert base.verifier_journal() == (True, None)


def test_un_admin_bloque_une_version_a_revoir(base):
    v = pipeline.decision_humaine(base, P, "reqeusts", "1.0", "bloquee", "typosquat confirmé",
                                  acteur="alice")
    assert v.etat is Etat.BLOQUEE
    assert base.lire_version(P, "reqeusts", "1.0").etat is Etat.BLOQUEE


@pytest.mark.parametrize("etat", [Etat.EN_ATTENTE, Etat.PUBLIEE, Etat.A_REVOIR])
def test_seules_approuver_ou_bloquer_sont_des_decisions(base, etat):
    with pytest.raises(ValueError):
        pipeline.decision_humaine(base, P, "reqeusts", "1.0", etat, "x", acteur="alice")


def test_on_ne_decide_que_sur_une_version_a_revoir(base):
    base.changer_etat(P, "reqeusts", "1.0", Etat.BLOQUEE, "veille")
    with pytest.raises(ValueError, match="à revoir"):
        pipeline.decision_humaine(base, P, "reqeusts", "1.0", Etat.APPROUVEE, "x", acteur="alice")
    with pytest.raises(KeyError):
        pipeline.decision_humaine(base, P, "inconnu", "1.0", Etat.APPROUVEE, "x", acteur="alice")


def test_une_raison_est_obligatoire(base):
    with pytest.raises(ValueError, match="raison"):
        pipeline.decision_humaine(base, P, "reqeusts", "1.0", Etat.APPROUVEE, "  ", acteur="a")


# --- la politique : un humain l'emporte sur FORT, jamais sur BLOQUANT ; seul un humain approuve ---

def approbation(source=Source.HUMAIN):
    return Signal(ecosysteme=P, nom="reqeusts", version="1.0", source=source, niveau=Niveau.INFO,
                  sorte="approbation_humaine", preuve={"extrait": "ok"})


def test_l_approbation_humaine_leve_un_signal_fort():
    assert politique.decider([signal(Niveau.FORT), approbation()]).etat is Etat.APPROUVEE


def test_l_approbation_humaine_ne_leve_jamais_un_signal_bloquant():
    bloquant = signal(Niveau.BLOQUANT, Source.SANDBOX, "lit_leurre")
    assert politique.decider([bloquant, approbation()]).etat is Etat.BLOQUEE


@pytest.mark.parametrize("source", [Source.LLM, Source.VEILLE, Source.STATIQUE, Source.SANDBOX])
def test_une_approbation_qui_ne_vient_pas_d_un_humain_ne_compte_pas(source):
    assert politique.decider([signal(Niveau.FORT), approbation(source)]).etat is Etat.A_REVOIR


def test_deux_decisions_simultanees_la_seconde_est_refusee(base, monkeypatch):
    """A4 : la seconde décision a lu la fiche « à revoir » avant que la première n'écrive."""
    perimee = base.fiche(P, "reqeusts", "1.0")
    pipeline.decision_humaine(base, P, "reqeusts", "1.0", Etat.BLOQUEE, "typosquat", acteur="bob")
    monkeypatch.setattr(base, "fiche", lambda *a: perimee)
    with pytest.raises(ValueError):
        pipeline.decision_humaine(base, P, "reqeusts", "1.0", Etat.APPROUVEE, "ok", acteur="alice")
    assert base.lire_version(P, "reqeusts", "1.0").etat is Etat.BLOQUEE
