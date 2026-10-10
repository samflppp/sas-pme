"""RAG local (M2) : les cas connus les plus proches d'une version, donnés au LLM comme données.

La requête est faite des constats (statique, sandbox), les plus graves d'abord. Les passages
servent au LLM à **expliquer** et à citer des cas réels ; ils ne décident rien. Sans index, ou
Ollama arrêté, l'analyse continue sans passages, et c'est journalisé.
"""
from pathlib import Path

from commun.modeles import RapportSandbox, Signal, Version
from plateforme.db.acces import Base
from plateforme.pipeline.rag import index as _index

TAILLE_REQUETE = 1500
N_PASSAGES = 5


def requete(v: Version, signaux: list[Signal], rapport: RapportSandbox) -> str:
    morceaux = [f"{v.ecosysteme.value} {v.nom}"]
    for s in sorted(signaux, key=lambda s: -s.niveau.rang):
        morceaux.append(f"{s.sorte} : {s.preuve.get('extrait', '')}")
    morceaux += [f"dns : {d}" for d in rapport.requetes_dns[:5]]
    morceaux += [f"leurre lu : {f}" for f in rapport.leurres_lus[:5]]
    return " ; ".join(morceaux)[:TAILLE_REQUETE]


def ouvrir(chemin: Path | None = None, plonger: _index.Plonger | None = None) -> _index.Index | None:
    """L'index de la plateforme, ou None s'il n'a pas été construit."""
    chemin = Path(chemin or _index.dossier())
    if not chemin.is_dir():
        return None
    ix = _index.Index(chemin, plonger or _index.plongeur_ollama("search_document"),
                      plonger or _index.plongeur_ollama("search_query"))
    return ix if ix.compter() else None


def passages(base: Base, v: Version, signaux: list[Signal], rapport: RapportSandbox, ix,
             n: int = N_PASSAGES) -> list[tuple[str, str]]:
    sujet = f"{v.ecosysteme.value}/{v.nom}/{v.version}"
    if ix is None:
        base.journaliser("rag", "rag_absent", sujet, {"dossier": str(_index.dossier())})
        return []
    try:
        return ix.chercher(requete(v, signaux, rapport), n=n)
    except Exception as e:  # noqa: BLE001 — sans passages, le LLM explique quand même
        base.journaliser("rag", "rag_indisponible", sujet, {"erreur": repr(e)[:300]})
        return []
