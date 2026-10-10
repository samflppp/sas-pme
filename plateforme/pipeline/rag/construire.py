"""Construit l'index du RAG sur la plateforme (une fois, puis pour le mettre à jour).

    python3 -I -m plateforme.pipeline.rag.construire                 # télécharge l'export OSV
    python3 -I -m plateforme.pipeline.rag.construire --osv all.zip   # export déjà téléchargé
    python3 -I -m plateforme.pipeline.rag.construire --malveillants  # MAL-… seuls (plus rapide)

Ollama doit tourner avec `nomic-embed-text` (`SAS_MODELE_EMBED`). L'index va dans `SAS_RAG`
(`rag_index` par défaut). Seul un téléchargement public sort vers Internet.
"""
import argparse
import sys
import tempfile
import time
from pathlib import Path

import httpx

from plateforme.pipeline.rag import documents, index

EXPORT_OSV = "https://osv-vulnerabilities.storage.googleapis.com/PyPI/all.zip"


def _telecharger(dossier: Path) -> Path:
    chemin = dossier / "pypi_all.zip"
    with httpx.Client(timeout=300, follow_redirects=True) as client, \
            client.stream("GET", EXPORT_OSV) as r:
        r.raise_for_status()
        with chemin.open("wb") as f:
            for morceau in r.iter_bytes():
                f.write(morceau)
    return chemin


def main(argv: list[str] | None = None, plonger: index.Plonger | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--osv", type=Path, help="export OSV de PyPI déjà téléchargé (all.zip)")
    p.add_argument("--dossier", type=Path, default=index.dossier())
    p.add_argument("--malveillants", action="store_true",
                   help="n'indexer que les paquets malveillants (MAL-…) et le référentiel")
    a = p.parse_args(argv)
    debut = time.monotonic()
    with tempfile.TemporaryDirectory() as tmp:
        osv = a.osv or _telecharger(Path(tmp))
        docs = [*documents.referentiel(),
                *documents.lire_osv(osv, malveillants_seuls=a.malveillants)]
    ix = index.Index(a.dossier, plonger or index.plongeur_ollama("search_document"))
    for i in range(0, len(docs), 1024):
        ix.ajouter(docs[i:i + 1024])
        print(f"  {min(i + 1024, len(docs))} / {len(docs)}", file=sys.stderr)
    print(f"{ix.compter()} documents indexés dans {a.dossier} "
          f"({time.monotonic() - debut:.0f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
