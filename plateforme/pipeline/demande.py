"""pipeline.demander (docs/contrats.md § 5) : la page « demander un paquet » de A l'appelle."""
import os
from datetime import datetime, timezone

import httpx
from packaging.utils import canonicalize_name

from commun.modeles import Ecosysteme, Etat, Version
from plateforme.db.acces import Base
from plateforme.pipeline import pypi


def demander(ecosysteme: Ecosysteme | str, nom: str, *, maintenant: datetime | None = None,
             base: Base | None = None) -> Version:
    """Choisit la dernière version publiée depuis plus de 3 jours et l'enregistre en attente.

    Le web appelle `demander(eco, nom)` sans base : on ouvre alors celle de SAS_DB, comme le web.
    Lève LookupError si le paquet est inconnu ou n'a aucune version assez ancienne,
    ValueError si le nom est invalide, NotImplementedError pour npm (extension du MVP).
    """
    if Ecosysteme(ecosysteme) is not Ecosysteme.PYPI:
        raise NotImplementedError("npm est une extension du MVP")
    nom = canonicalize_name(nom)  # « Typing_Extensions » et « typing-extensions » : une seule ligne
    maintenant = maintenant or datetime.now(timezone.utc)
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        choix = pypi.derniere_version_mure(nom, maintenant, client=client)
    if choix is None:
        raise LookupError(f"{nom} : aucune version publiée depuis plus de {pypi.DELAI.days} jours")
    version, publiee_le = choix
    v = Version(ecosysteme=Ecosysteme.PYPI, nom=nom, version=version, publiee_le=publiee_le,
                detectee_le=maintenant, etat=Etat.EN_ATTENTE)
    (base or Base(os.environ.get("SAS_DB", "sas.db"))).enregistrer_version(v)
    return v
