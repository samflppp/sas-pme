"""Index du RAG : Chroma persistant, embeddings calculés par Ollama local (`nomic-embed-text`).

Tout reste sur la plateforme : Ollama en local, Chroma sur disque, télémétrie de Chroma coupée.
"""
import os
from collections.abc import Callable, Sequence
from pathlib import Path

import httpx

from plateforme.pipeline.rag.documents import Document

TAILLE_PASSAGE = 500          # caractères par passage donné au LLM (5 passages ≈ 800 tokens)
LOT = 64
COLLECTION = "sas_rag"
REFERENTIEL = ["cwe", "capec", "attack", "rapport"]
N_REFERENTIEL = 2             # places réservées aux fiches CWE / CAPEC / ATT&CK
CANDIDATS = 8                 # candidats lus par place, pour écarter les textes répétés
Plonger = Callable[[list[str]], list[list[float]]]


def modele_embed() -> str:
    return os.environ.get("SAS_MODELE_EMBED", "").strip() or "nomic-embed-text"


def dossier() -> Path:
    return Path(os.environ.get("SAS_RAG", "").strip() or "rag_index")


def vecteurs(textes: Sequence[str], tache: str, *, client: httpx.Client, url: str,
             modele: str) -> list[list[float]]:
    """`tache` : « search_document » ou « search_query » (préfixes attendus par nomic)."""
    r = client.post(f"{url}/api/embed",
                    json={"model": modele, "input": [f"{tache}: {t}" for t in textes]})
    r.raise_for_status()
    return r.json()["embeddings"]


def plongeur_ollama(tache: str, *, url: str | None = None, modele: str | None = None) -> Plonger:
    from plateforme.pipeline import llm   # même Ollama que le LLM

    def plonger(textes: list[str]) -> list[list[float]]:
        with httpx.Client(timeout=300) as client:
            return vecteurs(textes, tache, client=client, url=url or llm.url(),
                            modele=modele or modele_embed())
    return plonger


class Index:
    def __init__(self, chemin: Path, plonger_documents: Plonger,
                 plonger_requete: Plonger | None = None):
        import chromadb
        from chromadb.config import Settings

        Path(chemin).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(chemin), settings=Settings(anonymized_telemetry=False))
        self.collection = self.client.get_or_create_collection(
            COLLECTION, embedding_function=None, metadata={"hnsw:space": "cosine"})
        self.plonger_documents = plonger_documents
        self.plonger_requete = plonger_requete or plonger_documents

    def compter(self) -> int:
        return self.collection.count()

    def ajouter(self, docs: Sequence[Document]) -> None:
        for i in range(0, len(docs), LOT):
            lot = docs[i:i + LOT]
            self.collection.upsert(ids=[d.ref for d in lot],
                                   embeddings=self.plonger_documents([d.texte for d in lot]),
                                   documents=[d.texte for d in lot],
                                   metadatas=[{"source": d.source} for d in lot])

    def _interroger(self, vecteur, n: int, ou: dict) -> list[tuple[str, str]]:
        r = self.collection.query(query_embeddings=vecteur, n_results=n, where=ou,
                                  include=["documents"])
        return list(zip(r["ids"][0], r["documents"][0]))

    def chercher(self, requete: str, n: int = 5) -> list[tuple[str, str]]:
        """Les cas connus les plus proches, un seul par texte (une campagne répète le sien sur
        des milliers d'avis), puis jusqu'à `N_REFERENTIEL` fiches CWE / CAPEC / ATT&CK."""
        vecteur = self.plonger_requete([requete])
        fiches = (self._interroger(vecteur, min(N_REFERENTIEL, n - 1),
                                   {"source": {"$in": REFERENTIEL}}) if n > 1 else [])
        cas, vus = [], set()
        for ref, texte in self._interroger(vecteur, n * CANDIDATS,
                                           {"source": {"$nin": REFERENTIEL}}):
            corps = texte.rstrip().rsplit("\n", 1)[-1]
            if corps not in vus:
                vus.add(corps)
                cas.append((ref, texte))
        return [(ref, texte[:TAILLE_PASSAGE]) for ref, texte in cas[:n - len(fiches)] + fiches]
