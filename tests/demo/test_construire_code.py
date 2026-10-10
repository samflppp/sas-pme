"""Corpus de la mesure du code (B) : échantillons Datadog choisis, sains peu connus."""
import importlib.util
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "construire_code", RACINE / "demo" / "corpus" / "construire_code.py")
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)

CHEMINS = [f"samples/pypi/malicious_intent/p{i:03d}/1.{i}/2025-01-01-p{i:03d}-v1.{i}.zip"
           for i in range(250)] + [
    "samples/pypi/compromised_lib/lib/2.0/2026-05-19-lib-v2.0.zip",
    "samples/pypi/compromised_lib/lib/2.1/2026-05-19-lib-v2.1.zip",
    "samples/npm/malicious_intent/x/1.0/2025-01-01-x-v1.0.zip",
    "samples/pypi/malicious_intent/p000/1.0/2025-02-01-p000-v1.0.zip",
]


def test_un_chemin_donne_nom_version_categorie():
    assert cc.lire_chemin(CHEMINS[-4]) == {
        "ecosysteme": "pypi", "nom": "lib", "version": "2.0", "categorie": "compromised_lib",
        "echantillon": CHEMINS[-4]}


def test_choix_deterministe_toutes_les_compromises_et_n_intentions_reparties():
    choix = cc.choisir_echantillons(CHEMINS, n=50)
    compromis = [e for e in choix if e["categorie"] == "compromised_lib"]
    intentions = [e for e in choix if e["categorie"] == "malicious_intent"]
    assert len(compromis) == 2 and len(intentions) == 50
    assert all(e["ecosysteme"] == "pypi" for e in choix)              # npm écarté
    assert len({(e["nom"], e["version"]) for e in choix}) == len(choix)
    assert intentions[0]["nom"] == "p000" and intentions[-1]["nom"] >= "p240"   # réparties
    assert cc.choisir_echantillons(list(reversed(CHEMINS)), n=50) == choix


def test_les_sains_peu_connus_sont_hors_des_populaires_et_espaces():
    liste = ["# en-tête"] + [f"paquet{i}" for i in range(5000)]
    noms = cc.choisir_peu_connus(liste, n=50, exclus={"paquet2000"})
    assert len(noms) == 50 and "paquet2000" not in noms
    rangs = [int(n.removeprefix("paquet")) for n in noms]
    assert min(rangs) >= 2000 and rangs == sorted(rangs) and rangs[1] - rangs[0] >= 50
