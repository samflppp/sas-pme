"""Pipeline d'analyse (B) : veille, délai, statique, LLM, RAG, politique."""
from plateforme.pipeline import politique, pypi, traitement
from plateforme.pipeline.demande import demander

__all__ = ["demander", "politique", "pypi", "traitement"]
