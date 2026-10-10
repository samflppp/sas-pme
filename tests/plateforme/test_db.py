import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from commun.modeles import (
    Ecosysteme, EntreeInventaire, Etat, Niveau, RapportSandbox, Signal, Source, Verdict, Version,
)
from plateforme.db.acces import Base

T0 = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
PY = Ecosysteme.PYPI


@pytest.fixture
def base(tmp_path) -> Base:
    return Base(str(tmp_path / "sas.db"))


def version(nom="requests", v="2.32.4", publiee=T0, etat=Etat.EN_ATTENTE) -> Version:
    return Version(ecosysteme=PY, nom=nom, version=v, publiee_le=publiee, detectee_le=publiee, etat=etat)


def signal(niveau=Niveau.FORT) -> Signal:
    return Signal(ecosysteme=PY, nom="requests", version="2.32.4", source=Source.STATIQUE,
                  niveau=niveau, sorte="typosquat", preuve={"proche_de": "requests"})


def test_enregistrer_version_dit_si_elle_est_nouvelle(base):
    assert base.enregistrer_version(version()) is True
    assert base.enregistrer_version(version()) is False
    assert base.lire_version(PY, "requests", "2.32.4").etat is Etat.EN_ATTENTE


def test_versions_a_traiter_attend_trois_jours(base):
    base.enregistrer_version(version(v="1.0", publiee=T0))
    base.enregistrer_version(version(v="2.0", publiee=T0 + timedelta(days=2)))
    base.enregistrer_version(version(v="3.0", publiee=T0, etat=Etat.APPROUVEE))
    pretes = base.versions_a_traiter(T0 + timedelta(days=3, minutes=1))
    assert [v.version for v in pretes] == ["1.0"]
    # le délai est réglable (mode démo)
    pretes = base.versions_a_traiter(T0 + timedelta(minutes=6), delai=timedelta(minutes=5))
    assert [v.version for v in pretes] == ["1.0"]


def test_changer_etat_et_lister(base):
    base.enregistrer_version(version())
    base.changer_etat(PY, "requests", "2.32.4", Etat.PUBLIEE, "approuvée et signée")
    assert base.lire_version(PY, "requests", "2.32.4").etat is Etat.PUBLIEE
    assert [v.nom for v in base.lister_versions(etat=Etat.PUBLIEE)] == ["requests"]
    assert base.lister_versions(etat=Etat.BLOQUEE) == []


def test_changer_etat_d_une_version_inconnue_echoue(base):
    with pytest.raises(KeyError):
        base.changer_etat(PY, "inconnu", "1.0", Etat.BLOQUEE, "x")


def test_signaux_verdict_et_rapport_se_relisent(base):
    base.enregistrer_version(version())
    sid = base.ajouter_signal(signal())
    assert isinstance(sid, int)
    verdict = Verdict(etat=Etat.A_REVOIR, raison="Un nom très proche de requests.", signaux=[signal()])
    vid = base.enregistrer_verdict(PY, "requests", "2.32.4", verdict)
    rapport = RapportSandbox(requetes_dns=["exfil.demo.invalid"], connexions=[], fichiers_sensibles=[],
                             leurres_lus=[], processus=["python"], code_sortie=0, duree_s=1.0,
                             delai_depasse=False)
    base.enregistrer_rapport_sandbox(PY, "requests", "2.32.4", rapport)

    fiche = base.fiche(PY, "requests", "2.32.4")
    assert fiche.signaux == [signal()]
    assert fiche.signaux[0].preuve == {"proche_de": "requests"}
    assert fiche.verdict == verdict and fiche.verdict_id == vid
    assert fiche.rapport_sandbox == rapport


def test_inventaire_remplace_l_instantane_precedent(base):
    e = dict(telechargements=3, dernier=T0)
    base.enregistrer_inventaire([EntreeInventaire(ecosysteme=PY, nom="requests", version="2.31.0", **e),
                                 EntreeInventaire(ecosysteme=Ecosysteme.NPM, nom="left-pad", version="1.3.0", **e)])
    base.enregistrer_inventaire([EntreeInventaire(ecosysteme=PY, nom="requests", version="2.32.4", **e)])
    assert base.inventaire() == [(PY, "requests", "2.32.4")]


def test_un_inventaire_refuse_ne_laisse_pas_la_base_bloquee(base, tmp_path):
    """B, A2 : sans ROLLBACK, la transaction restait ouverte et plus rien n'était validé."""
    e = dict(ecosysteme=PY, telechargements=1, dernier=T0)
    base.enregistrer_inventaire([EntreeInventaire(nom="requests", version="2.31.0", **e)])
    double = EntreeInventaire(nom="urllib3", version="2.2.0", **e)
    with pytest.raises(sqlite3.IntegrityError):
        base.enregistrer_inventaire([double, double])
    assert base.inventaire() == [(PY, "requests", "2.31.0")]   # l'ancien instantané reste
    base.enregistrer_version(version())
    autre = Base(str(tmp_path / "sas.db"))                      # une autre connexion voit l'écriture
    assert autre.lire_version(PY, "requests", "2.32.4") is not None
    assert autre.verifier_journal() == (True, None)


def test_le_journal_garde_chaque_changement_et_se_verifie(base, tmp_path):
    base.enregistrer_version(version())
    base.changer_etat(PY, "requests", "2.32.4", Etat.BLOQUEE, "signal bloquant")
    base.enregistrer_verdict(PY, "requests", "2.32.4",
                             Verdict(etat=Etat.BLOQUEE, raison="r", signaux=[]))
    actions = [e.action for e in base.journal()]
    assert actions == ["version_detectee", "etat_change", "verdict"]
    assert base.verifier_journal() == (True, None)

    # un attaquant qui a le fichier retire le garde-fou et falsifie une entrée : la chaîne casse
    with sqlite3.connect(tmp_path / "sas.db") as c:
        c.execute("DROP TRIGGER journal_sans_modification")
        c.execute("UPDATE journal SET charge = '{\"etat\":\"approuvee\"}' WHERE seq = 2")
    assert base.verifier_journal() == (False, 2)


def test_le_journal_refuse_modification_et_suppression(base, tmp_path):
    base.enregistrer_version(version())
    with sqlite3.connect(tmp_path / "sas.db") as c:
        with pytest.raises(sqlite3.DatabaseError):
            c.execute("DELETE FROM journal")
        with pytest.raises(sqlite3.DatabaseError):
            c.execute("UPDATE journal SET acteur = 'x'")
