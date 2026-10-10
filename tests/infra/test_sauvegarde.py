"""Sauvegardes (docs/sauvegardes.md, M2) : restic local chiffré. Le test de restauration exigé :
effacer la base, la restaurer, vérifier que la chaîne du journal est intacte."""

import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from commun.modeles import Ecosysteme, Etat, Version
from plateforme.db.acces import Base

SCRIPT = Path(__file__).resolve().parents[2] / "infra" / "sauvegarde.sh"
RESTIC = shutil.which("restic") or str(Path.home() / ".local/bin/restic")
pytestmark = pytest.mark.skipif(not os.access(RESTIC, os.X_OK), reason="restic absent")


def _env(tmp_path, base: Path) -> dict:
    (tmp_path / "mdp").write_text("mot-de-passe-du-depot-de-test\n")
    (tmp_path / "conf").mkdir(exist_ok=True)
    (tmp_path / "conf" / "relais_autorises.txt").write_text("api.github.com\n")
    return {**os.environ, "PATH": f"{Path(RESTIC).parent}:{os.environ['PATH']}",
            "RESTIC_REPOSITORY": str(tmp_path / "depot"), "RESTIC_PASSWORD_FILE": str(tmp_path / "mdp"),
            "SAS_PYTHON": sys.executable, "SAS_DB": str(base), "SAS_SAUVEGARDE_DOSSIERS": str(tmp_path / "conf")}


def _sh(env, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True,
                          timeout=120)


def _remplir(chemin: Path) -> None:
    base = Base(str(chemin))
    maintenant = datetime.now(timezone.utc)
    for i in range(3):
        base.enregistrer_version(Version(ecosysteme=Ecosysteme.PYPI, nom="requests", version=f"2.{i}",
                                         publiee_le=maintenant, detectee_le=maintenant,
                                         etat=Etat.EN_ATTENTE))
    base.changer_etat(Ecosysteme.PYPI, "requests", "2.0", Etat.BLOQUEE, "test")


def test_effacer_restaurer_et_la_chaine_du_journal_est_intacte(tmp_path):
    chemin = tmp_path / "sas.db"
    _remplir(chemin)
    avant = Base(str(chemin)).compter_journal()
    env = _env(tmp_path, chemin)
    r = _sh(env, "sauver")
    assert r.returncode == 0, r.stderr
    for f in tmp_path.glob("sas.db*"):          # effacer la base (et ses fichiers WAL)
        f.unlink()
    (tmp_path / "conf" / "relais_autorises.txt").unlink()
    r = _sh(env, "restaurer")
    assert r.returncode == 0, r.stderr
    base = Base(str(chemin))
    assert base.verifier_journal() == (True, None)
    assert base.compter_journal() == avant > 0
    assert base.lire_version(Ecosysteme.PYPI, "requests", "2.0").etat == Etat.BLOQUEE
    assert (tmp_path / "conf" / "relais_autorises.txt").read_text() == "api.github.com\n"
    r = _sh(env, "verifier")
    assert r.returncode == 0 and "journal intact" in r.stdout, r.stdout + r.stderr


def test_le_depot_est_chiffre(tmp_path):
    chemin = tmp_path / "sas.db"
    _remplir(chemin)
    env = _env(tmp_path, chemin)
    assert _sh(env, "sauver").returncode == 0
    contenu = b"".join(f.read_bytes() for f in (tmp_path / "depot").rglob("*") if f.is_file())
    assert b"requests" not in contenu and b"api.github.com" not in contenu


def test_la_cle_de_signature_n_entre_jamais_dans_la_sauvegarde(tmp_path):
    chemin = tmp_path / "sas.db"
    _remplir(chemin)
    env = _env(tmp_path, chemin)
    (tmp_path / "conf" / "signature.pem").write_text("CLE PRIVEE")
    assert _sh(env, "sauver").returncode == 0
    (tmp_path / "conf" / "signature.pem").unlink()
    assert _sh(env, "restaurer").returncode == 0
    assert not (tmp_path / "conf" / "signature.pem").exists()


def test_un_journal_altere_fait_echouer_la_verification(tmp_path):
    chemin = tmp_path / "sas.db"
    _remplir(chemin)
    import sqlite3
    c = sqlite3.connect(chemin)
    c.execute("DROP TRIGGER IF EXISTS journal_sans_modification")
    for (nom,) in c.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall():
        c.execute(f"DROP TRIGGER {nom}")
    c.execute("UPDATE journal SET acteur = 'attaquant' WHERE seq = 1")
    c.commit()
    c.close()
    r = _sh(_env(tmp_path, chemin), "verifier")
    assert r.returncode != 0 and "journal ALTÉRÉ" in r.stdout


def test_sans_mot_de_passe_du_depot_le_script_refuse(tmp_path):
    env = _env(tmp_path, tmp_path / "sas.db")
    del env["RESTIC_PASSWORD_FILE"]
    r = _sh(env, "sauver")
    assert r.returncode != 0 and "RESTIC_PASSWORD_FILE" in r.stderr
