"""Vérifie le vrai LLM sur des versions de PyPI (B, H16) : ses signaux, et le verdict qui en sort.

À lancer sur la plateforme, Ollama démarré, depuis la racine du dépôt :

    python3 -m mesure.llm_paquet certifi==2026.7.22 idna==3.20 --rag

Pour chaque version : téléchargement depuis PyPI (sha256 vérifié), contrôles statiques réels
(archives lues comme données, jamais exécutées), puis le LLM avec le RAG, comme dans le pipeline.
La sandbox n'est pas lancée : le rapport est vide, comme pour une version qui n'y fait rien.
Affiche chaque signal du LLM (et s'il a été redescendu faute de preuve tirée du paquet) et le
verdict de la politique. Code de sortie 1 si une réponse du LLM sort du schéma ou n'arrive pas.
"""
import argparse
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx

from commun.modeles import Ecosysteme, Etat, RapportSandbox, Version
from plateforme.db.acces import Base
from plateforme.pipeline import llm, politique, pypi, rag
from plateforme.pipeline.statique.code import controler_code

P = Ecosysteme.PYPI
VIDE = RapportSandbox(requetes_dns=[], connexions=[], fichiers_sensibles=[], leurres_lus=[],
                      processus=[], code_sortie=0, duree_s=0.0, delai_depasse=False)


@dataclass
class Essai:
    nom: str
    version: str
    duree_s: float
    conforme: bool
    verdict: str
    raison: str
    signaux_llm: list[str] = field(default_factory=list)
    explication: str = ""
    refs: list[str] = field(default_factory=list)


def _signal(s) -> str:
    texte = f"{s.niveau.value} {s.sorte}"
    if s.preuve.get("non_ancre"):
        return texte + " (non ancré : redescendu de fort)"
    if s.preuve.get("sans_constat"):
        return texte + " (sans constat statique ni sandbox : redescendu de fort)"
    return texte


def verifier(specs: list[str], client: httpx.Client, url: str, modele: str, dossier: Path,
             ix=None, pypi_base: str | None = None) -> list[Essai]:
    base = Base(str(dossier / "verif_llm.db"))
    essais = []
    for spec in specs:
        nom, version = spec.split("==")
        archives = pypi.telecharger(nom, version, dossier / f"{nom}-{version}", client=client,
                                    base=pypi_base or pypi.BASE)
        maintenant = datetime.now(timezone.utc)
        v = Version(ecosysteme=P, nom=nom, version=version, publiee_le=maintenant,
                    detectee_le=maintenant, etat=Etat.EN_ANALYSE)
        signaux = controler_code(P, nom, version, archives)
        avant = len(base.journal())
        debut = time.monotonic()
        passages = rag.passages(base, v, signaux, VIDE, ix) if ix else []
        r = llm.analyser(base, v, signaux, VIDE, client=client, url=url, modele=modele,
                         passages=passages)
        duree = time.monotonic() - debut
        echecs = [e for e in base.journal()[avant:] if e.action.startswith("llm_")]
        verdict = politique.decider([*signaux, *r.signaux])
        essais.append(Essai(nom, version, duree, not echecs, verdict.etat.value, verdict.raison,
                            [_signal(s) for s in r.signaux], r.explication, r.refs_rag))
    return essais


def main(argv: list[str] | None = None, dossier: Path | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("versions", nargs="+", help="nom==version, ex. certifi==2026.7.22")
    p.add_argument("--modele", default=llm.modele())
    p.add_argument("--url", default=llm.url())
    p.add_argument("--rag", action="store_true", help="passages de l'index du RAG (SAS_RAG)")
    a = p.parse_args(argv)
    if any(s.count("==") != 1 for s in a.versions):
        print("Écrire chaque version sous la forme nom==version.")
        return 2
    ix = rag.ouvrir() if a.rag else None
    if a.rag and ix is None:
        print("Index du RAG absent : python3 -I -m plateforme.pipeline.rag.construire")
        return 1
    with tempfile.TemporaryDirectory() as tmp, httpx.Client(timeout=600) as client:
        essais = verifier(a.versions, client, a.url.rstrip("/"), a.modele, dossier or Path(tmp),
                          ix)
    print(f"Modèle {a.modele} ({a.url})")
    for e in essais:
        etat = "conforme" if e.conforme else "HORS SCHÉMA OU INJOIGNABLE"
        print(f"- {e.nom} {e.version} : verdict {e.verdict} ({etat}, LLM {e.duree_s:.1f} s)")
        print(f"  raison  : {e.raison}")
        print(f"  LLM     : {', '.join(e.signaux_llm) or 'aucun signal'}")
        print(f"  phrase  : {e.explication or '(vide)'}")
        if a.rag:
            print(f"  cite    : {', '.join(e.refs) or 'rien'}")
    return 0 if all(e.conforme for e in essais) else 1


if __name__ == "__main__":
    sys.exit(main())
