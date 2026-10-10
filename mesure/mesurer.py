"""Mesure (B) : détection et fausses alertes des contrôles sur le corpus demo/corpus/corpus.json.

Une version est « détectée » si au moins un signal est FORT ou BLOQUANT : la politique la met alors
« à revoir » ou « bloquée », donc elle n'atteint pas les serveurs. Un signal MOYEN ne suffit pas.

Ligne 1, nom seul, sur le corpus OpenSSF : seuls le nom et la version sont lus.
Ligne 2, contrôles statiques (nom + code), sur demo/corpus/corpus_code.json : échantillons
malveillants de Datadog **lus seulement** (jamais installés ni exécutés), et vraies archives des
versions saines, comparées à leur version précédente comme dans le pipeline.

    python3 -I mesure/mesurer.py                                  # ligne 1 seulement
    # ligne 2 : les échantillons choisis, dans un dossier à part (voir construire_code.py)
    python3 -I -c "import json; print('\\n'.join(e['echantillon'] for e in json.load(open(
        'demo/corpus/corpus_code.json'))['malveillants']))" \\
        | xargs git -C <dossier>/dd checkout HEAD --
    python3 -I mesure/mesurer.py --echantillons <dossier>/dd --cache <dossier>/archives
"""
import argparse
import importlib.util
import json
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from commun.modeles import Ecosysteme, Niveau, Signal

RACINE = Path(__file__).resolve().parents[1]
# None : version non mesurable (archive introuvable ou illisible), hors du compte et listée.
Detecteur = Callable[[Ecosysteme, str, str], list[Signal] | None]


@dataclass
class Resultat:
    malveillants: int = 0
    detectes: int = 0
    sains: int = 0
    fausses_alertes: int = 0
    manques: list[str] = field(default_factory=list)
    alertes_a_tort: list[str] = field(default_factory=list)
    preuves: dict[str, list[str]] = field(default_factory=dict)
    non_mesures: list[str] = field(default_factory=list)

    @property
    def taux_detection(self) -> float:
        return self.detectes / self.malveillants if self.malveillants else 0.0

    @property
    def taux_fausses_alertes(self) -> float:
        return self.fausses_alertes / self.sains if self.sains else 0.0


def _arrete(signaux: list[Signal]) -> bool:
    return any(s.niveau.rang >= Niveau.FORT.rang for s in signaux)


def _id(e: dict) -> str:
    return f"{e['nom']} {e['version']}"


def mesurer(corpus: dict, detecteur: Detecteur) -> Resultat:
    r = Resultat()
    for e in corpus["malveillants"]:
        signaux = detecteur(Ecosysteme(e["ecosysteme"]), e["nom"], e["version"])
        if signaux is None:
            r.non_mesures.append(_id(e))
            continue
        r.malveillants += 1
        if _arrete(signaux):
            r.detectes += 1
            r.preuves[_id(e)] = _preuves(signaux)
        else:
            r.manques.append(_id(e))
    for e in corpus["sains"]:
        signaux = detecteur(Ecosysteme(e["ecosysteme"]), e["nom"], e["version"])
        if signaux is None:
            r.non_mesures.append(_id(e))
            continue
        r.sains += 1
        if _arrete(signaux):
            r.fausses_alertes += 1
            r.alertes_a_tort.append(_id(e))
            r.preuves[_id(e)] = _preuves(signaux)
    return r


def _preuves(signaux: list[Signal]) -> list[str]:
    """Les preuves des signaux qui arrêtent la version (FORT ou plus), les plus graves d'abord."""
    forts = sorted((s for s in signaux if s.niveau.rang >= Niveau.FORT.rang),
                   key=lambda s: -s.niveau.rang)
    return [f"{s.sorte} : {s.preuve.get('extrait', '')[:120]}".rstrip(" :") for s in forts[:3]]


def _pc(n: int, total: int) -> str:
    return f"{n} / {total} ({round(100 * n / total) if total else 0} %)"


def tableau(colonnes: dict[str, Resultat]) -> str:
    lignes = ["| Contrôles | Détection (malveillantes arrêtées) | Fausses alertes (saines arrêtées) |",
              "|---|---|---|"]
    lignes += [f"| {nom} | {_pc(r.detectes, r.malveillants)} | {_pc(r.fausses_alertes, r.sains)} |"
               for nom, r in colonnes.items()]
    return "\n".join(lignes)


LIMITES = """## Limites

- **Ligne 1 :** 26 des 30 paquets du corpus OpenSSF n'existent plus sur PyPI ; seuls leur nom et
  leur version sont lus. Les 50 saines sont des paquets populaires, donc dans la liste du contrôle
  de typosquat : leurs 0 % de fausses alertes sont acquis par construction.
- **Ligne 2, détection :** les échantillons de Datadog sont plus anciens (2022 à 2026) que le corpus
  OpenSSF, et souvent des campagnes en série (mêmes auteurs, même code). Les bibliothèques
  compromises sont analysées en entier, sans leur version saine précédente : le pipeline, lui, ne
  regarderait que ce qui change.
- **Ligne 2, fausses alertes :** les règles ont été réglées sur 20 paquets populaires sains, dont
  plusieurs sont dans les 50 « populaires » : ce groupe est donc optimiste. Le groupe « peu
  connus » n'a servi à aucun réglage : c'est le chiffre honnête.
- Une version arrêtée n'est pas jetée : un signal FORT la met « à revoir » (un humain tranche),
  seul un signal BLOQUANT la bloque. Une fausse alerte coûte donc une revue, pas une panne.
- Ne sont pas comptés : les métadonnées (signaux MOYEN au plus, sans effet sur l'arrêt), la veille
  OSV (le corpus vient des mêmes listes : 100 % par construction), le délai de 3 jours (il faudrait
  la date de retrait de chaque version).
"""


def rapport(corpus: dict, colonnes: dict[str, Resultat], notes: str = "") -> str:
    parties = [
        "# Mesure sur le corpus",
        "",
        f"Généré le {datetime.now(timezone.utc):%Y-%m-%d} par `python3 -I mesure/mesurer.py`, "
        f"sur `demo/corpus/corpus.json` (généré le {corpus.get('genere_le', '?')}) et, pour la "
        "ligne 2, `demo/corpus/corpus_code.json`.",
        "",
        tableau(colonnes),
        "",
        "Une version est arrêtée si un contrôle lève un signal FORT ou BLOQUANT.",
    ]
    for nom, r in colonnes.items():
        parties += ["", f"## {nom}", "", "**Arrêtées :**"]
        parties += [f"- `{n}` : {' ; '.join(p)}" for n, p in r.preuves.items()] or ["- aucune"]
        parties += ["", f"**Malveillantes manquées ({len(r.manques)}) :** "
                    + ", ".join(f"`{n}`" for n in r.manques)]
        if r.alertes_a_tort:
            parties += ["", f"**Saines arrêtées à tort ({len(r.alertes_a_tort)}) :** "
                        + ", ".join(f"`{n}`" for n in r.alertes_a_tort)]
        if r.non_mesures:
            parties += ["", f"**Non mesurées ({len(r.non_mesures)}), hors du compte :** "
                        + ", ".join(f"`{n}`" for n in r.non_mesures)]
    if notes:
        parties += ["", notes]
    parties += ["", LIMITES]
    return "\n".join(parties)


def _module(nom: str):
    spec = importlib.util.spec_from_file_location(nom, RACINE / "mesure" / f"{nom}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _par_groupe(corpus: dict, r: Resultat) -> str:
    lignes = ["## Fausses alertes par groupe (ligne 2)", ""]
    for groupe in ("populaire", "peu_connu"):
        noms = [_id(e) for e in corpus["sains"] if e.get("groupe") == groupe
                and _id(e) not in r.non_mesures]
        tort = [n for n in r.alertes_a_tort if n in noms]
        lignes.append(f"- {groupe.replace('_', ' ')}s : {_pc(len(tort), len(noms))}"
                      + (f" ({', '.join(f'`{n}`' for n in tort)})" if tort else ""))
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> None:
    from plateforme.pipeline.statique.nom import controler_nom
    p = argparse.ArgumentParser(description="Mesure des contrôles sur le corpus.")
    p.add_argument("--echantillons", type=Path, help="clone du jeu de Datadog (ligne 2)")
    p.add_argument("--cache", type=Path, help="dossier à part pour les archives saines")
    a = p.parse_args(argv)
    corpus = json.loads((RACINE / "demo" / "corpus" / "corpus.json").read_text(encoding="utf-8"))
    colonnes = {"Nom seul (typosquat), corpus OpenSSF": mesurer(corpus, controler_nom)}
    notes = ""
    if a.echantillons:
        import httpx

        from plateforme.pipeline import pypi
        code = json.loads((RACINE / "demo" / "corpus" / "corpus_code.json")
                          .read_text(encoding="utf-8"))
        with httpx.Client(timeout=120, follow_redirects=True) as client:
            detecteur = _module("statique").detecteur(
                code, echantillons=a.echantillons,
                cache=a.cache or Path(tempfile.mkdtemp(prefix="sas-mesure-")),
                telecharger=lambda n, v, d: pypi.telecharger(n, v, d, client=client))
            r = mesurer(code, detecteur)
        colonnes["Contrôles statiques (nom + code), Datadog + sains"] = r
        notes = _par_groupe(code, r)
        if detecteur.illisibles:
            notes += "\n\n**Illisibles :** " + " ; ".join(
                f"`{k}` ({v})" for k, v in detecteur.illisibles.items())
        if detecteur.sans_precedente:
            notes += ("\n\n**Sans version précédente (code analysé en entier) :** "
                      + ", ".join(f"`{n}`" for n in detecteur.sans_precedente))
    sortie = RACINE / "mesure" / "resultats.md"
    sortie.write_text(rapport(corpus, colonnes, notes), encoding="utf-8")
    print(tableau(colonnes))
    if notes:
        print(notes)


if __name__ == "__main__":
    main()
