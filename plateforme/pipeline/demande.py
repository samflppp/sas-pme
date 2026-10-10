"""pipeline.demander (docs/contrats.md § 5) : la page « demander un paquet » de A l'appelle."""
from collections.abc import Callable
from datetime import datetime, timezone

import httpx

from commun.modeles import Ecosysteme, Etat, Version
from plateforme.pipeline import pypi


def demander(ecosysteme: Ecosysteme, nom: str, *, maintenant: datetime | None = None,
             enregistrer: Callable[[Version], bool] | None = None) -> Version:
    """Choisit la dernière version publiée depuis plus de 3 jours et l'enregistre en attente.

    Lève LookupError si le paquet est inconnu ou n'a aucune version assez ancienne.
    """
    if ecosysteme is not Ecosysteme.PYPI:
        raise NotImplementedError("npm est une extension du MVP")
    if enregistrer is None:  # vrai accès de A, importé tard tant qu'il n'est pas sur main
        from plateforme.db.acces import enregistrer_version as enregistrer
    maintenant = maintenant or datetime.now(timezone.utc)
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        choix = pypi.derniere_version_mure(nom, maintenant, client=client)
    if choix is None:
        raise LookupError(f"{nom} : aucune version publiée depuis plus de {pypi.DELAI.days} jours")
    version, publiee_le = choix
    v = Version(ecosysteme=ecosysteme, nom=nom, version=version, publiee_le=publiee_le,
                detectee_le=maintenant, etat=Etat.EN_ATTENTE)
    enregistrer(v)
    return v
