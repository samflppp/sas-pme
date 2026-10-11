"""Pipeline d'analyse (B) : veille, délai, statique, LLM, RAG, politique."""
from plateforme.pipeline import npm, politique, pypi, traitement
from plateforme.pipeline.decision import decision_humaine
from plateforme.pipeline.demande import demander

__all__ = ["decision_humaine", "demander", "npm", "politique", "pypi", "traitement"]
