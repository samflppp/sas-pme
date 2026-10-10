"""Construit demo/corpus/corpus_code.json : le corpus de la mesure du code (contrôles statiques).

- **Malveillants :** des échantillons du jeu de Datadog (malicious-software-packages-dataset), qui
  garde le code de paquets retirés de PyPI depuis : toutes les bibliothèques compromises
  (`compromised_lib`), plus `n` paquets malveillants (`malicious_intent`) pris à intervalle régulier
  dans la liste triée. Seule la liste des chemins est lue ici, aucun échantillon.
- **Sains :** les 50 mises à jour populaires de corpus.json, plus 50 paquets **peu connus** (rangs
  2 000 à 5 000 des plus téléchargés), dernière mise à jour stable de plus de 30 jours.

Usage (Python isolé ; seuls les chemins sont listés, sans télécharger les échantillons) :
    git clone --depth 1 --filter=blob:none --no-checkout \\
        https://github.com/DataDog/malicious-software-packages-dataset <dossier>/dd
    git -C <dossier>/dd ls-tree -r --name-only HEAD samples/pypi > <dossier>/chemins.txt
    python3 -I demo/corpus/construire_code.py <dossier>/chemins.txt
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
SORTIE = ICI / "corpus_code.json"
POPULAIRES_PYPI = RACINE / "plateforme" / "pipeline" / "donnees" / "populaires_pypi.txt"
SOURCE = "https://github.com/DataDog/malicious-software-packages-dataset"


def _construire():
    spec = importlib.util.spec_from_file_location("construire", ICI / "construire.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lire_chemin(chemin: str) -> dict | None:
    """samples/<eco>/<catégorie>/<nom>/<version>/<fichier>.zip -> une entrée, ou None."""
    parties = PurePosixPath(chemin).parts
    if len(parties) != 6 or parties[0] != "samples" or not parties[5].endswith(".zip"):
        return None
    _, eco, categorie, nom, version, _ = parties
    return {"ecosysteme": eco, "nom": nom, "version": version, "categorie": categorie,
            "echantillon": chemin}


def choisir_echantillons(chemins: list[str], n: int = 100) -> list[dict]:
    entrees, vus = [], set()
    for e in map(lire_chemin, sorted(chemins)):
        if e and e["ecosysteme"] == "pypi" and (e["nom"], e["version"]) not in vus:
            vus.add((e["nom"], e["version"]))
            entrees.append(e)
    compromis = [e for e in entrees if e["categorie"] == "compromised_lib"]
    intentions = [e for e in entrees if e["categorie"] == "malicious_intent"]
    if len(intentions) > n:
        intentions = [intentions[round(i * len(intentions) / n)] for i in range(n)]
    return compromis + intentions


def choisir_peu_connus(lignes: list[str], n: int = 50, exclus: set[str] = frozenset(),
                       debut: int = 2000) -> list[str]:
    """`n` noms espacés régulièrement à partir du rang `debut` (rang 0 = le plus téléchargé)."""
    noms = [l.strip() for l in lignes if l.strip() and not l.startswith("#")][debut:]
    pas, choix = len(noms) // n, []
    for i in range(n):
        for nom in noms[i * pas:(i + 1) * pas]:
            if nom.lower() not in exclus:
                choix.append(nom)
                break
    return choix


def main(fichier_chemins: str) -> None:
    construire = _construire()
    chemins = Path(fichier_chemins).read_text(encoding="utf-8").splitlines()
    malveillants = choisir_echantillons(chemins)
    corpus = json.loads((ICI / "corpus.json").read_text(encoding="utf-8"))
    populaires = [{**e, "groupe": "populaire"} for e in corpus["sains"]]
    exclus = {p.lower() for p in construire.POPULAIRES} | {e["nom"].lower() for e in malveillants}
    limite = datetime.now(timezone.utc) - timedelta(days=construire.AGE_MIN_SAIN_J)
    peu_connus = []
    for nom in choisir_peu_connus(POPULAIRES_PYPI.read_text(encoding="utf-8").splitlines(),
                                  exclus=exclus):
        try:
            e = construire.choisir_sain(nom, construire._pypi_json(nom), limite)
        except OSError as erreur:
            print(f"  {nom} : {erreur}", file=sys.stderr)
            continue
        if e:
            peu_connus.append({**e, "groupe": "peu_connu"})
    sortie = {
        "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {"malveillants": f"{SOURCE} (samples/pypi, zips chiffrés, mot de passe "
                                    "« infected »)",
                    "sains": "corpus.json (populaires) et populaires_pypi.txt, rangs 2000+"},
        "avertissement": "Échantillons malveillants réels : les lire seulement, avec Python en "
        "-I, dans un dossier à part. Ne jamais les installer ni les exécuter hors de la sandbox.",
        "malveillants": malveillants,
        "sains": populaires + peu_connus,
    }
    SORTIE.write_text(json.dumps(sortie, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(malveillants)} malveillants, {len(populaires)} + {len(peu_connus)} sains -> "
          f"{SORTIE}")


if __name__ == "__main__":
    main(sys.argv[1])
