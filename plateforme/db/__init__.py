"""Base de la plateforme (A). Utiliser `Base` de `plateforme.db.acces`."""
from plateforme.db.acces import Base, EntreeJournal, Fiche

__all__ = ["Base", "EntreeJournal", "Fiche"]
