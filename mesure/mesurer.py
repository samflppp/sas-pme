"""Mesure (B) : détection et fausses alertes, en trois lignes qui ajoutent chacune une couche du
pipeline (contrôles seuls ; + sandbox ; + LLM/RAG), sur demo/corpus/corpus_code.json.

Une version est « détectée » si au moins un signal est FORT ou BLOQUANT : la politique la met alors
« à revoir » ou « bloquée », donc elle n'atteint pas les serveurs. Un signal MOYEN ne suffit pas.

- Ligne 1 : nom + code. Échantillons malveillants de Datadog **lus seulement** ; vraies archives
  des versions saines, comparées à leur version précédente comme dans le pipeline.
- Ligne 2 : + le rapport de la sandbox de C. Les échantillons n'y sont installés et importés que
  dans la sandbox (`mesure/sandbox.py`) ; chaque rapport est gardé dans `<cache>/rapports`.
- Ligne 3 : + le LLM avec le RAG (Ollama, sur la plateforme), là où il peut changer le résultat.
- Annexe : le nom seul sur le corpus OpenSSF (demo/corpus/corpus.json).

    # les échantillons choisis, dans un dossier à part (voir demo/corpus/construire_code.py)
    python3 -I -c "import json; print('\\n'.join(e['echantillon'] for e in json.load(open(
        'demo/corpus/corpus_code.json'))['malveillants']))" \\
        | xargs git -C <dossier>/dd checkout HEAD --
    python3 -I mesure/mesurer.py --echantillons <dossier>/dd --cache <dossier>/cache            # 1
    python3 -I mesure/mesurer.py --echantillons <dossier>/dd --cache <dossier>/cache --sandbox  # 1-2
    python3 -I mesure/mesurer.py --echantillons <dossier>/dd --cache <dossier>/cache --llm      # 1-3
"""
import argparse
import importlib.util
import json
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from commun.modeles import Ecosysteme, Niveau, Signal, Source

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


class avec_sandbox:
    """Colonne 2 : les contrôles, plus les signaux du rapport de sandbox (règles du pipeline).

    Une analyse impossible (sandbox en échec) arrête la version, comme dans le pipeline, qui la met
    « à revoir » plutôt que de l'approuver sans analyse ; elle est listée à part (`impossibles`).
    """

    def __init__(self, controles: Detecteur, rapport: Callable[[Ecosysteme, str, str], object]):
        self.controles, self.rapport, self.impossibles = controles, rapport, []

    def __call__(self, eco: Ecosysteme, nom: str, version: str) -> list[Signal] | None:
        from plateforme.pipeline.sandbox_signaux import signaux_sandbox
        signaux = self.controles(eco, nom, version)
        if signaux is None:
            return None
        try:
            return signaux + signaux_sandbox(eco, nom, version, self.rapport(eco, nom, version))
        except Exception as e:  # noqa: BLE001 — comme traitement.traiter : « analyse impossible »
            self.impossibles.append(f"{nom} {version}")
            return signaux + [Signal(ecosysteme=eco, nom=nom, version=version,
                                     source=Source.SANDBOX, niveau=Niveau.FORT,
                                     sorte="analyse_impossible", preuve={"extrait": str(e)[:200]})]


class avec_llm:
    """Colonne 3 : plus les signaux du LLM (avec le RAG), validés par `plateforme.pipeline.llm`.

    Le LLM n'est interrogé que là où il peut changer le résultat : une version pas encore arrêtée,
    avec au moins un constat MOYEN hors du LLM. Ailleurs, rien ne peut changer : le LLM n'abaisse
    jamais un risque, et sans ce constat son signal FORT redescend à MOYEN (règle du pipeline).
    """

    def __init__(self, avant: Detecteur, llm: Callable[..., list[Signal]]):
        self.avant, self.llm, self.appels = avant, llm, 0

    def __call__(self, eco: Ecosysteme, nom: str, version: str) -> list[Signal] | None:
        signaux = self.avant(eco, nom, version)
        if signaux is None or _arrete(signaux) or not any(
                s.source is not Source.LLM and s.niveau.rang >= Niveau.MOYEN.rang
                for s in signaux):
            return signaux
        self.appels += 1
        return signaux + self.llm(eco, nom, version, signaux)


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

- **Détection :** les échantillons de Datadog (2022 à 2026) sont souvent des campagnes en série
  (mêmes auteurs, même code). Les bibliothèques compromises sont analysées en entier, sans leur
  version saine précédente : le pipeline, lui, ne regarderait que ce qui change.
- **Fausses alertes :** les règles statiques ont été réglées sur 20 paquets populaires sains, dont
  plusieurs sont dans les 50 « populaires » : ce groupe est optimiste. Le groupe « peu connus »
  n'a servi à aucun réglage : c'est le chiffre honnête.
- **Sandbox (ligne 2) :**
  - même scénario que le produit : conteneur Linux sans réseau réel, leurres, `strace`,
    **battement de 60 s** après l'import ;
  - les échantillons de Datadog sont dépliés : ils sont remis en sdist (s'il y a un `setup.py` ou
    un `pyproject.toml`) ou en roue, à partir de leurs fichiers, sans rien exécuter hors de la
    sandbox (`mesure/sandbox.py`) ;
  - comme le produit, la sandbox installe **sans les dépendances** (`--no-deps`) : une version qui
    a besoin des siennes pour s'importer échoue à l'import, et la sandbox n'observe alors que son
    installation. C'est le cas de **40 des 98 versions saines** et de **12 des 25 malveillantes
    manquées** (dont ultralytics, dont la charge part à l'import). Le 0 % de fausses alertes vaut
    pour ce que la sandbox a pu observer ;
  - les paquets qui visent Windows (`ctypes.windll`, PowerShell) n'agissent pas dans un conteneur
    Linux ; certains sont vus quand même, parce qu'ils lancent `powershell` ;
  - mesurée hors de la plateforme AWS, avec une image construite du même Dockerfile, à un détail
    près : `strace` copié de l'hôte, le miroir Debian étant bloqué. Les rapports sont gardés dans
    `mesure/rapports_sandbox/`.
- **LLM/RAG (ligne 3) :** le LLM n'est interrogé que là où il peut changer le résultat (voir la note
  plus haut) ; il tourne sur la plateforme (Ollama, `qwen2.5-coder:7b`, index du RAG).
- **Annexe, nom seul, corpus OpenSSF :** 26 des 30 paquets n'existent plus sur PyPI ; seuls leur nom
  et leur version sont lus. Les 50 saines sont des paquets populaires, donc dans la liste du
  contrôle de typosquat : leurs 0 % de fausses alertes sont acquis par construction.
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
        f"Généré le {datetime.now(timezone.utc):%Y-%m-%d} par `python3 -I mesure/mesurer.py`, sur "
        "`demo/corpus/corpus_code.json` (échantillons malveillants de Datadog et versions saines "
        "réelles de PyPI). Chaque ligne ajoute une couche du pipeline à la précédente.",
        "",
        tableau(colonnes),
        "",
        "Une version est arrêtée si un signal est FORT ou BLOQUANT : la politique la met « à revoir » "
        "ou « bloquée », donc elle n'atteint pas les serveurs.",
    ]
    avant: Resultat | None = None
    for nom, r in colonnes.items():
        deja = set(avant.preuves) if avant else set()
        nouvelles = {n: p for n, p in r.preuves.items() if n not in deja}
        parties += ["", f"## {nom}", "",
                    "**Arrêtées :**" if avant is None else "**Arrêtées en plus de la ligne précédente :**"]
        parties += [f"- `{n}` : {' ; '.join(p)}" for n, p in nouvelles.items()] or ["- aucune"]
        parties += ["", f"**Malveillantes manquées ({len(r.manques)}) :** "
                    + (", ".join(f"`{n}`" for n in r.manques) or "aucune")]
        if r.alertes_a_tort:
            parties += ["", f"**Saines arrêtées à tort ({len(r.alertes_a_tort)}) :** "
                        + ", ".join(f"`{n}`" for n in r.alertes_a_tort)]
        if r.non_mesures:
            parties += ["", f"**Non mesurées ({len(r.non_mesures)}), hors du compte :** "
                        + ", ".join(f"`{n}`" for n in r.non_mesures)]
        avant = r
    if notes:
        parties += ["", notes]
    parties += ["", LIMITES]
    return "\n".join(parties)


def annexe_texte(annexe: dict[str, Resultat]) -> str:
    """La mesure d'origine du nom seul, sur le corpus OpenSSF (30 malveillantes, 50 saines)."""
    parties = ["## Annexe : nom seul, corpus OpenSSF (`demo/corpus/corpus.json`)", "",
               tableau(annexe)]
    for r in annexe.values():
        parties += ["", "Arrêtées : " + (", ".join(f"`{n}`" for n in r.preuves) or "aucune")]
    return "\n".join(parties)


def _module(nom: str):
    spec = importlib.util.spec_from_file_location(nom, RACINE / "mesure" / f"{nom}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _par_groupe(corpus: dict, colonnes: dict[str, Resultat]) -> str:
    lignes = ["## Fausses alertes par groupe de versions saines", "",
              "| Ligne | populaires | peu connus |", "|---|---|---|"]
    for nom, r in colonnes.items():
        cases = []
        for groupe in ("populaire", "peu_connu"):
            noms = [_id(e) for e in corpus["sains"] if e.get("groupe") == groupe
                    and _id(e) not in r.non_mesures]
            cases.append(_pc(len([n for n in r.alertes_a_tort if n in noms]), len(noms)))
        lignes.append(f"| {nom} | {' | '.join(cases)} |")
    return "\n".join(lignes)


COL1 = "1. Contrôles seuls (nom + code)"
COL2 = "2. + sandbox"
COL3 = "3. + LLM/RAG"


def _memoriser(detecteur: Detecteur) -> Detecteur:
    """Les contrôles d'une version ne sont calculés (et ses archives téléchargées) qu'une fois."""
    vus: dict[tuple[str, str], list[Signal] | None] = {}

    def memo(eco: Ecosysteme, nom: str, version: str) -> list[Signal] | None:
        if (nom, version) not in vus:
            vus[(nom, version)] = detecteur(eco, nom, version)
        return vus[(nom, version)]
    memo.__dict__.update(detecteur.__dict__)
    return memo


def _preparer(corpus: dict, executeur, paralleles: int, exclus: list[str]) -> None:
    """Lance la sandbox sur tout le corpus, plusieurs à la fois ; chaque rapport va au cache."""
    import sys
    from concurrent.futures import ThreadPoolExecutor
    entrees = [e for e in [*corpus["malveillants"], *corpus["sains"]] if _id(e) not in exclus]

    def une(e: dict) -> None:
        try:
            executeur(Ecosysteme(e["ecosysteme"]), e["nom"], e["version"])
        except Exception as erreur:  # noqa: BLE001 — retentée, puis notée par avec_sandbox
            print(f"[sandbox] {_id(e)} : {str(erreur)[:120]}", file=sys.stderr)
    with ThreadPoolExecutor(max(1, paralleles)) as pool:
        for n, _ in enumerate(pool.map(une, entrees), 1):
            print(f"[sandbox] {n} / {len(entrees)}", file=sys.stderr, flush=True)


def _llm(executeur, cache: Path, client, ix):
    """Le LLM du pipeline (avec le RAG), sur les constats et le rapport de sandbox de la version."""
    from commun.modeles import Etat, Version
    from plateforme.db.acces import Base
    from plateforme.pipeline import llm, rag
    base = Base(str(cache / "mesure_llm.db"))

    def appeler(eco: Ecosysteme, nom: str, version: str, signaux: list[Signal]) -> list[Signal]:
        maintenant = datetime.now(timezone.utc)
        v = Version(ecosysteme=eco, nom=nom, version=version, publiee_le=maintenant,
                    detectee_le=maintenant, etat=Etat.EN_ANALYSE)
        rapport = executeur(eco, nom, version)
        passages = rag.passages(base, v, signaux, rapport, ix)
        return llm.analyser(base, v, signaux, rapport, client=client, url=llm.url(),
                            modele=llm.modele(), passages=passages).signaux
    return appeler


def main(argv: list[str] | None = None) -> None:
    from plateforme.pipeline.statique.nom import controler_nom
    p = argparse.ArgumentParser(description="Mesure des contrôles sur le corpus.")
    p.add_argument("--echantillons", type=Path, help="clone du jeu de Datadog")
    p.add_argument("--cache", type=Path, help="dossier à part : archives, rapports de sandbox")
    p.add_argument("--sandbox", action="store_true",
                   help="colonne 2 : chaque version dans la sandbox de C (Docker)")
    p.add_argument("--paralleles", type=int, default=3, help="analyses de sandbox à la fois")
    p.add_argument("--llm", action="store_true",
                   help="colonne 3 : + LLM/RAG (Ollama et l'index du RAG, sur la plateforme)")
    a = p.parse_args(argv)
    corpus = json.loads((RACINE / "demo" / "corpus" / "corpus.json").read_text(encoding="utf-8"))
    annexe = {"Nom seul (typosquat), corpus OpenSSF": mesurer(corpus, controler_nom)}
    colonnes: dict[str, Resultat] = {}
    notes = []
    if a.echantillons:
        import httpx

        from plateforme.pipeline import pypi
        code = json.loads((RACINE / "demo" / "corpus" / "corpus_code.json")
                          .read_text(encoding="utf-8"))
        cache = a.cache or Path(tempfile.mkdtemp(prefix="sas-mesure-"))
        with httpx.Client(timeout=600, follow_redirects=True) as client:
            def telecharger(nom: str, version: str, dossier: Path) -> list[Path]:
                if dossier.is_dir() and (deja := sorted(
                        f for f in dossier.iterdir() if f.name.endswith((".whl", ".tar.gz", ".zip")))):
                    return deja
                return pypi.telecharger(nom, version, dossier, client=client)

            brut = _module("statique").detecteur(code, echantillons=a.echantillons, cache=cache,
                                                  telecharger=telecharger)
            controles = _memoriser(brut)
            colonnes[COL1] = r1 = mesurer(code, controles)
            if brut.illisibles:
                notes.append("**Illisibles :** " + " ; ".join(
                    f"`{k}` ({v})" for k, v in brut.illisibles.items()))
            if brut.sans_precedente:
                notes.append("**Sans version précédente (code analysé en entier) :** "
                             + ", ".join(f"`{n}`" for n in brut.sans_precedente))
            if a.sandbox or a.llm:
                from plateforme.sandbox import executer
                executeur = _module("sandbox").Executeur(
                    code, echantillons=a.echantillons, cache=cache, executer=executer,
                    archives_saines=lambda n, v: telecharger(n, v, cache / n / v))
                if a.sandbox:
                    _preparer(code, executeur, a.paralleles, r1.non_mesures)
                avec = avec_sandbox(controles, executeur)
                colonnes[COL2] = mesurer(code, avec)
                if avec.impossibles:
                    notes.append(f"**Sandbox impossible ({len(avec.impossibles)}), comptées "
                                 "arrêtées comme dans le pipeline :** "
                                 + ", ".join(f"`{n}`" for n in avec.impossibles))
            if a.llm:
                from plateforme.pipeline import rag
                ix = rag.ouvrir()
                if ix is None:
                    raise SystemExit("Index du RAG absent : python3 -I -m "
                                     "plateforme.pipeline.rag.construire")
                d3 = avec_llm(avec, _llm(executeur, cache, client, ix))
                colonnes[COL3] = mesurer(code, d3)
                notes.append(f"**LLM interrogé sur {d3.appels} versions** : celles qui n'étaient "
                             "pas encore arrêtées et avaient un constat MOYEN hors du LLM. Ailleurs, "
                             "il ne peut rien changer (voir `avec_llm`).")
    if colonnes:
        notes.insert(0, _par_groupe(code, colonnes))
    notes.append(annexe_texte(annexe))
    sortie = RACINE / "mesure" / "resultats.md"
    sortie.write_text(rapport(corpus, colonnes or annexe, "\n\n".join(notes)), encoding="utf-8")
    print(tableau(colonnes or annexe))


if __name__ == "__main__":
    main()
