"""Vérifie le vrai LLM sur la démo (B) : format `VerdictLLM` respecté, durée, phrase obtenue.

À lancer sur la plateforme, Ollama démarré et le modèle tiré (`ollama pull qwen2.5-coder:7b`) :

    python3 -m mesure.llm_demo                                   # SAS_MODELE, sinon le 7B
    python3 -m mesure.llm_demo --modele qwen2.5-coder:3b         # le repli, pour comparer
    python3 -m mesure.llm_demo --rag                             # avec l'index du RAG (SAS_RAG)

Pour `demo-horodatage` 1.1 (saine) puis 1.2 (piégée), il envoie au LLM exactement ce que le
pipeline lui envoie : les constats statiques réels (archives du faux PyPI, lues comme données,
jamais exécutées) et le rapport de la sandbox v1 au format de C (rien pour 1.1 ; DNS vers
l'attaquant et leurre lu pour 1.2). Code de sortie 1 si une réponse sort du schéma ou n'arrive pas.
"""
import argparse
import importlib.util
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx

from commun.modeles import Ecosysteme, Etat, RapportSandbox, Version
from plateforme.db.acces import Base
from plateforme.pipeline import llm, rag
from plateforme.pipeline.sandbox_signaux import signaux_sandbox
from plateforme.pipeline.statique.code import controler_code

RACINE = Path(__file__).resolve().parents[1]
P = Ecosysteme.PYPI
_VIDE = dict(requetes_dns=[], connexions=[], fichiers_sensibles=[], leurres_lus=[], processus=[],
             code_sortie=0, duree_s=3.0, delai_depasse=False)
RAPPORTS = {
    "1.1": RapportSandbox(**_VIDE),
    "1.2": RapportSandbox(**{**_VIDE, "requetes_dns": ["collecte.attaquant-demo.invalid"],
                             "connexions": ["collecte.attaquant-demo.invalid:443"],
                             "fichiers_sensibles": ["~/.aws/credentials"],
                             "leurres_lus": ["~/.aws/credentials",
                                             "~/.aws/credentials (exfiltré)"]}),
}


@dataclass
class Essai:
    version: str
    duree_s: float
    conforme: bool
    erreur: str = ""
    signaux: list[str] = field(default_factory=list)
    explication: str = ""
    refs: list[str] = field(default_factory=list)


def _faux_pypi():
    spec = importlib.util.spec_from_file_location(
        "faux_pypi", RACINE / "demo" / "paquets" / "faux_pypi.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verifier(client: httpx.Client, url: str, modele: str, dossier: Path,
             ix=None) -> list[Essai]:
    fp = _faux_pypi()
    base = Base(str(dossier / "verif_llm.db"))
    archives = {}
    for v, fichiers in fp.construire().items():
        (dossier / v).mkdir(exist_ok=True)
        archives[v] = [dossier / v / n for n in fichiers]
        for chemin, octets in zip(archives[v], fichiers.values()):
            chemin.write_bytes(octets)
    essais = []
    for v, precedente in (("1.1", "1.0"), ("1.2", "1.1")):
        maintenant = datetime.now(timezone.utc)
        version = Version(ecosysteme=P, nom=fp.NOM, version=v, publiee_le=maintenant,
                          detectee_le=maintenant, etat=Etat.EN_ANALYSE)
        signaux = (controler_code(P, fp.NOM, v, archives[v], precedentes=archives[precedente])
                   + signaux_sandbox(P, fp.NOM, v, RAPPORTS[v]))
        avant = len(base.journal())
        debut = time.monotonic()
        passages = rag.passages(base, version, signaux, RAPPORTS[v], ix) if ix else []
        r = llm.analyser(base, version, signaux, RAPPORTS[v], client=client, url=url,
                         modele=modele, passages=passages)
        duree = time.monotonic() - debut
        echecs = [e for e in base.journal()[avant:] if e.action.startswith("llm_")]
        essais.append(Essai(v, duree, not echecs,
                            erreur=echecs[0].action if echecs else "",
                            signaux=[f"{s.niveau.value} {s.sorte}" for s in r.signaux],
                            explication=r.explication, refs=r.refs_rag))
    return essais


def main(argv: list[str] | None = None, dossier: Path | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--modele", default=llm.modele())
    p.add_argument("--url", default=llm.url())
    p.add_argument("--rag", action="store_true", help="passages de l'index du RAG (SAS_RAG)")
    a = p.parse_args(argv)
    ix = rag.ouvrir() if a.rag else None
    if a.rag and ix is None:
        print("Index du RAG absent : python3 -I -m plateforme.pipeline.rag.construire")
        return 1
    with tempfile.TemporaryDirectory() as tmp, httpx.Client(timeout=600) as client:
        essais = verifier(client, a.url.rstrip("/"), a.modele, dossier or Path(tmp), ix)
    print(f"Modèle {a.modele} ({a.url})")
    for e in essais:
        etat = ("conforme" if e.conforme else
                "HORS SCHÉMA" if e.erreur == "llm_hors_schema" else f"ÉCHEC ({e.erreur})")
        print(f"- demo-horodatage {e.version} : {etat}, {e.duree_s:.1f} s")
        print(f"  signaux : {', '.join(e.signaux) or 'aucun'}")
        print(f"  phrase  : {e.explication or '(vide)'}")
        if a.rag:
            print(f"  cite    : {', '.join(e.refs) or 'rien'}")
    return 0 if all(e.conforme for e in essais) else 1


if __name__ == "__main__":
    sys.exit(main())
