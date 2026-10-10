"""Mesure, colonne « + sandbox » (B, M3) : chaque version passe dans la sandbox de C.

Les échantillons sont remis en archive installable **sans rien exécuter** ici : déchiffrés, leurs
fichiers recopiés dans un sdist (s'il y a de quoi construire : `setup.py` est un vecteur d'attaque,
il doit tourner dans la sandbox) ou dans une roue. Seule la sandbox les installe et les importe.
"""
import base64
import hashlib
import importlib.util
import io
import json
import tarfile
import zipfile
from pathlib import Path

from commun.modeles import Ecosysteme, RapportSandbox

RACINE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("sandbox_mesure", RACINE / "mesure" / "sandbox.py")
sm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sm)

P = Ecosysteme.PYPI
PREFIXE = "tmp/tmpab12/evil/"


def echantillon(chemin: Path, fichiers: dict[str, str]) -> Path:
    with zipfile.ZipFile(chemin, "w") as z:
        for nom, texte in fichiers.items():
            z.writestr(nom, texte)
    return chemin


def test_un_echantillon_avec_setup_py_devient_un_sdist(tmp_path):
    e = echantillon(tmp_path / "e.zip", {PREFIXE + "setup.py": "from setuptools import setup\n",
                                         PREFIXE + "evil/__init__.py": "X = 1\n",
                                         PREFIXE + "package_info-evil-1.0.json": "{}"})
    a = sm.reemballer(e, "evil", "1.0", tmp_path / "sortie")
    assert a.name == "evil-1.0.tar.gz"
    with tarfile.open(a) as t:
        assert sorted(t.getnames()) == ["evil-1.0/evil/__init__.py", "evil-1.0/setup.py"]


def test_une_roue_depliee_redevient_une_roue_installable(tmp_path):
    info = PREFIXE + "evil_pkg-2.0.dist-info/"
    e = echantillon(tmp_path / "e.zip", {PREFIXE + "evil.pth": "import os\n",
                                         PREFIXE + "evil_pkg/__init__.py": "X = 1\n",
                                         info + "METADATA": "Name: evil-pkg\nVersion: 2.0\n",
                                         info + "RECORD": "faux,sha256=xx,1\n"})
    a = sm.reemballer(e, "evil-pkg", "2.0", tmp_path / "sortie")
    assert a.name == "evil_pkg-2.0-py3-none-any.whl"
    with zipfile.ZipFile(a) as z:
        noms = set(z.namelist())
        assert {"evil.pth", "evil_pkg/__init__.py", "evil_pkg-2.0.dist-info/METADATA",
                "evil_pkg-2.0.dist-info/WHEEL", "evil_pkg-2.0.dist-info/RECORD"} <= noms
        # RECORD réécrit : chaque hash correspond, sinon pip refuserait la roue.
        for ligne in z.read("evil_pkg-2.0.dist-info/RECORD").decode().splitlines():
            chemin, h, _ = ligne.split(",")
            if h:
                attendu = base64.urlsafe_b64encode(hashlib.sha256(z.read(chemin)).digest())
                assert h == "sha256=" + attendu.rstrip(b"=").decode()


def test_sans_metadonnees_on_fabrique_une_roue_minimale(tmp_path):
    e = echantillon(tmp_path / "e.zip", {"var/x/evil/evil/__init__.py": "X = 1\n",
                                         "var/x/evil/evil/mod.py": "Y = 2\n"})
    a = sm.reemballer(e, "evil", "3.0", tmp_path / "sortie")
    with zipfile.ZipFile(a) as z:
        assert {"evil/__init__.py", "evil/mod.py", "evil-3.0.dist-info/METADATA"} <= set(
            z.namelist())


def test_une_archive_d_origine_est_reprise_telle_quelle(tmp_path):
    roue = io.BytesIO()
    with zipfile.ZipFile(roue, "w") as z:
        z.writestr("evil/__init__.py", "X = 1\n")
        z.writestr("evil-1.0.dist-info/METADATA", "Name: evil\n")
    e = echantillon(tmp_path / "e.zip", {})
    with zipfile.ZipFile(e, "w") as z:
        z.writestr("2026-03-24-evil-v1.0.zip", roue.getvalue())
    a = sm.reemballer(e, "evil", "1.0", tmp_path / "sortie")
    assert a.suffix == ".whl" and a.read_bytes() == roue.getvalue()


CORPUS = {"malveillants": [{"ecosysteme": "pypi", "nom": "evil", "version": "1.0",
                            "echantillon": "evil.zip"}],
          "sains": [{"ecosysteme": "pypi", "nom": "bon", "version": "2.0"}]}
VIDE = RapportSandbox(requetes_dns=[], connexions=[], fichiers_sensibles=[], leurres_lus=[],
                      processus=[], code_sortie=0, duree_s=1.0, delai_depasse=False)


def test_l_executeur_lance_la_sandbox_comme_le_pipeline_et_garde_le_rapport(tmp_path):
    echantillon(tmp_path / "evil.zip", {PREFIXE + "setup.py": "from setuptools import setup\n"})
    bon = tmp_path / "bon"
    bon.mkdir()
    (bon / "bon-2.0.tar.gz").write_bytes(b"sdist")
    (bon / "bon-2.0-py3-none-any.whl").write_bytes(b"roue")
    appels = []

    def executer(eco, archive, module, duree_max_s=120):
        appels.append((eco, Path(archive).name, module))
        return VIDE.model_copy(update={"requetes_dns": [f"vu.{module}.invalid"]})

    ex = sm.Executeur(CORPUS, echantillons=tmp_path, cache=tmp_path / "cache", executer=executer,
                      archives_saines=lambda nom, version: sorted(bon.iterdir()))
    assert ex(P, "evil", "1.0").requetes_dns == ["vu.evil.invalid"]
    assert ex(P, "bon", "2.0").requetes_dns == ["vu.bon.invalid"]
    # La roue d'abord, comme le pipeline ; le module est le nom avec « _ ».
    assert appels == [(P, "evil-1.0.tar.gz", "evil"), (P, "bon-2.0-py3-none-any.whl", "bon")]
    # Rapport gardé : une seconde mesure (ou la colonne LLM, sur AWS) ne relance pas la sandbox.
    ex2 = sm.Executeur(CORPUS, echantillons=tmp_path, cache=tmp_path / "cache",
                       executer=lambda *a, **k: 1 / 0, archives_saines=lambda n, v: [])
    assert ex2(P, "evil", "1.0").requetes_dns == ["vu.evil.invalid"]
    assert json.loads((tmp_path / "cache" / "rapports" / "evil-1.0.json").read_text())
