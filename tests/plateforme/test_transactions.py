"""B, A3 et A4 : écritures concurrentes sur la base.

A3 : deux `Base` sur le même fichier (uvicorn à plusieurs workers, un script lancé pendant que le
web tourne) lisaient le dernier hash hors transaction : la chaîne cassait.
A4 : `changer_etat` ne vérifiait pas l'état de départ, et le journal partait dans une autre
transaction : un « approuver » écrasait un « bloquer » arrivé juste avant."""
import threading
from datetime import datetime, timezone

import pytest

from commun.modeles import Ecosysteme, Etat, Version
from plateforme.db.acces import Base

T0 = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
PY = Ecosysteme.PYPI


def version(base: Base, etat: Etat = Etat.A_REVOIR) -> None:
    base.enregistrer_version(Version(ecosysteme=PY, nom="piege", version="1.0", publiee_le=T0,
                                     detectee_le=T0, etat=Etat.EN_ATTENTE))
    base.changer_etat(PY, "piege", "1.0", etat, "pour le test")


def test_deux_bases_sur_le_meme_fichier_gardent_la_chaine(tmp_path):
    chemin = str(tmp_path / "sas.db")
    bases = [Base(chemin), Base(chemin)]
    par_base = 150

    def ecrire(b: Base, n: int) -> None:
        for i in range(par_base):
            b.journaliser(f"processus-{n}", "essai", f"sujet-{i}", {"i": i})

    fils = [threading.Thread(target=ecrire, args=(b, n)) for n, b in enumerate(bases)]
    for f in fils:
        f.start()
    for f in fils:
        f.join()
    assert bases[0].compter_journal() == 2 * par_base
    assert Base(chemin).verifier_journal() == (True, None)


def test_changer_etat_refuse_si_l_etat_a_change_entre_temps(tmp_path):
    base = Base(str(tmp_path / "sas.db"))
    version(base)
    base.changer_etat(PY, "piege", "1.0", Etat.BLOQUEE, "admin-1 : bloquer", acteur="admin-1",
                      attendu=Etat.A_REVOIR)
    avant = base.compter_journal()
    with pytest.raises(ValueError, match="bloquee"):
        base.changer_etat(PY, "piege", "1.0", Etat.APPROUVEE, "admin-2 : approuver",
                          acteur="admin-2", attendu=Etat.A_REVOIR)
    assert base.lire_version(PY, "piege", "1.0").etat is Etat.BLOQUEE   # la première décision tient
    assert base.compter_journal() == avant                                 # rien au journal


def test_changer_etat_sans_etat_attendu_reste_comme_avant(tmp_path):
    base = Base(str(tmp_path / "sas.db"))
    version(base, Etat.BLOQUEE)
    base.changer_etat(PY, "piege", "1.0", Etat.APPROUVEE, "pipeline")
    assert base.lire_version(PY, "piege", "1.0").etat is Etat.APPROUVEE


def test_changer_etat_une_version_inconnue(tmp_path):
    base = Base(str(tmp_path / "sas.db"))
    with pytest.raises(KeyError):
        base.changer_etat(PY, "absent", "1.0", Etat.BLOQUEE, "x", attendu=Etat.A_REVOIR)


def test_l_etat_et_son_journal_partent_ensemble(tmp_path, monkeypatch):
    """Si l'écriture au journal échoue, le changement d'état est annulé avec elle."""
    base = Base(str(tmp_path / "sas.db"))
    version(base)

    def panne(*a, **k):
        raise OSError("disque plein")

    monkeypatch.setattr(base, "_journaliser", panne)
    with pytest.raises(OSError):
        base.changer_etat(PY, "piege", "1.0", Etat.BLOQUEE, "bloquer")
    assert base.lire_version(PY, "piege", "1.0").etat is Etat.A_REVOIR
