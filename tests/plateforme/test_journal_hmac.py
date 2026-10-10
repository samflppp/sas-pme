"""B, A1 : le journal est signé en HMAC avec une clé hors de la base (SAS_CLE_JOURNAL).

Qui a la base sans la clé ne peut plus réécrire une entrée et recalculer la chaîne."""
import hashlib
import json
from datetime import datetime, timezone

import pytest

from commun.modeles import Ecosysteme, Etat, Version
from plateforme.db.acces import Base

T0 = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
PY = Ecosysteme.PYPI
CLE = "une-cle-de-journal-de-test-assez-longue"


def remplir(base: Base) -> None:
    base.enregistrer_version(Version(ecosysteme=PY, nom="piege", version="1.0", publiee_le=T0,
                                     detectee_le=T0, etat=Etat.EN_ATTENTE))
    base.changer_etat(PY, "piege", "1.0", Etat.BLOQUEE, "Bloquée : exfiltration.")
    base.journaliser("admin", "connexion", "web", {})


def test_une_chaine_recalculee_sans_la_cle_se_voit(tmp_path):
    """L'attaque reproduite par B : DROP TRIGGER, « bloquée » réécrit en « approuvée », chaîne
    recalculée en sha256 (sans clé). verifier_journal() rendait (True, None)."""
    base = Base(str(tmp_path / "sas.db"), cle_journal=CLE)
    remplir(base)
    c = base._c
    c.execute("DROP TRIGGER journal_sans_modification")
    c.execute("""UPDATE journal SET charge='{"etat":"approuvee","raison":"ok"}' WHERE seq=2""")
    prec = "0" * 64
    for r in c.execute("SELECT * FROM journal ORDER BY seq").fetchall():
        corps = json.dumps([r["a"], r["acteur"], r["action"], r["sujet"], r["charge"]],
                           ensure_ascii=False, separators=(",", ":"))
        h = hashlib.sha256((prec + corps).encode("utf-8")).hexdigest()
        c.execute("UPDATE journal SET prec=?, hash=? WHERE seq=?", (prec, h, r["seq"]))
        prec = h
    assert base.verifier_journal() == (False, 1)


def test_la_meme_cle_relit_la_chaine(tmp_path):
    remplir(Base(str(tmp_path / "sas.db"), cle_journal=CLE))
    assert Base(str(tmp_path / "sas.db"), cle_journal=CLE).verifier_journal() == (True, None)


def test_une_autre_cle_ne_relit_pas_la_chaine(tmp_path):
    remplir(Base(str(tmp_path / "sas.db"), cle_journal=CLE))
    autre = Base(str(tmp_path / "sas.db"), cle_journal="une-autre-cle-de-journal-assez-longue")
    assert autre.verifier_journal() == (False, 1)


def test_la_cle_vient_de_l_environnement(tmp_path, monkeypatch):
    monkeypatch.setenv("SAS_CLE_JOURNAL", CLE)
    remplir(Base(str(tmp_path / "sas.db")))
    assert Base(str(tmp_path / "sas.db"), cle_journal=CLE).verifier_journal() == (True, None)


@pytest.mark.parametrize("cle", [None, "", "trop-courte"])
def test_sans_cle_suffisante_la_base_refuse_de_demarrer(tmp_path, monkeypatch, cle):
    monkeypatch.delenv("SAS_CLE_JOURNAL", raising=False)
    if cle is not None:
        monkeypatch.setenv("SAS_CLE_JOURNAL", cle)
    with pytest.raises(RuntimeError, match="SAS_CLE_JOURNAL"):
        Base(str(tmp_path / "sas.db"))
