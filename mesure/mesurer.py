"""Mesure (B) : détection et fausses alertes des contrôles sur le corpus demo/corpus/corpus.json.

Une version est « détectée » si au moins un signal est FORT ou BLOQUANT : la politique la met alors
« à revoir » ou « bloquée », donc elle n'atteint pas les serveurs. Un signal MOYEN ne suffit pas.

Ne télécharge ni n'exécute aucun échantillon : seuls le nom et la version sont lus.

    python3 -m mesure.mesurer            # écrit mesure/resultats.md
"""
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from commun.modeles import Ecosysteme, Niveau, Signal

RACINE = Path(__file__).resolve().parents[1]
Detecteur = Callable[[Ecosysteme, str, str], list[Signal]]


@dataclass
class Resultat:
    malveillants: int = 0
    detectes: int = 0
    sains: int = 0
    fausses_alertes: int = 0
    manques: list[str] = field(default_factory=list)
    alertes_a_tort: list[str] = field(default_factory=list)
    preuves: dict[str, list[str]] = field(default_factory=dict)

    @property
    def taux_detection(self) -> float:
        return self.detectes / self.malveillants if self.malveillants else 0.0

    @property
    def taux_fausses_alertes(self) -> float:
        return self.fausses_alertes / self.sains if self.sains else 0.0


def _arrete(signaux: list[Signal]) -> bool:
    return any(s.niveau.rang >= Niveau.FORT.rang for s in signaux)


def mesurer(corpus: dict, detecteur: Detecteur) -> Resultat:
    r = Resultat()
    for e in corpus["malveillants"]:
        signaux = detecteur(Ecosysteme(e["ecosysteme"]), e["nom"], e["version"])
        r.malveillants += 1
        if _arrete(signaux):
            r.detectes += 1
            r.preuves[e["nom"]] = [s.preuve.get("extrait", s.sorte) for s in signaux]
        else:
            r.manques.append(e["nom"])
    for e in corpus["sains"]:
        signaux = detecteur(Ecosysteme(e["ecosysteme"]), e["nom"], e["version"])
        r.sains += 1
        if _arrete(signaux):
            r.fausses_alertes += 1
            r.alertes_a_tort.append(e["nom"])
            r.preuves[e["nom"]] = [s.preuve.get("extrait", s.sorte) for s in signaux]
    return r


def _pc(n: int, total: int) -> str:
    return f"{n} / {total} ({round(100 * n / total) if total else 0} %)"


def tableau(colonnes: dict[str, Resultat]) -> str:
    lignes = ["| Contrôles | Détection (malveillantes arrêtées) | Fausses alertes (saines arrêtées) |",
              "|---|---|---|"]
    lignes += [f"| {nom} | {_pc(r.detectes, r.malveillants)} | {_pc(r.fausses_alertes, r.sains)} |"
               for nom, r in colonnes.items()]
    return "\n".join(lignes)


LIMITES = """## Limites

- 26 des 30 paquets malveillants n'existaient plus sur PyPI le 2026-10-10. Sans télécharger leurs
  archives (interdit hors sandbox), seuls leur nom et leur version sont lus. Les contrôles sur le code
  (installation, `exec`/`base64`, domaines) et la sandbox se mesureront sur `demo/paquets/`.
- Les 50 versions saines sont des paquets populaires, donc dans la liste du contrôle de typosquat :
  leurs 0 % de fausses alertes sont acquis par construction. Il faudra des paquets sains peu connus.
- Le contrôle « présent dans OpenSSF malicious-packages » n'est pas compté : le corpus vient de cette
  même liste, il détecterait 100 % par construction.
- Le délai de 3 jours n'est pas compté ici : il faudrait la date de publication de chaque version
  malveillante sur PyPI, que le rapport OpenSSF ne donne pas toujours.
"""


def rapport(corpus: dict, colonnes: dict[str, Resultat]) -> str:
    parties = [
        "# Mesure sur le corpus",
        "",
        f"Généré le {datetime.now(timezone.utc):%Y-%m-%d} par `python3 -m mesure.mesurer`, sur "
        f"`demo/corpus/corpus.json` (généré le {corpus.get('genere_le', '?')}).",
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
    parties += ["", LIMITES]
    return "\n".join(parties)


def main() -> None:
    from plateforme.pipeline.statique.nom import controler_nom
    corpus = json.loads((RACINE / "demo" / "corpus" / "corpus.json").read_text(encoding="utf-8"))
    colonnes = {"Contrôles seuls (nom : typosquat)": mesurer(corpus, controler_nom)}
    sortie = RACINE / "mesure" / "resultats.md"
    sortie.write_text(rapport(corpus, colonnes), encoding="utf-8")
    print(tableau(colonnes))


if __name__ == "__main__":
    main()
