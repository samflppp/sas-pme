"""pipeline.demander (docs/contrats.md § 5) : la page « demander un paquet » de A l'appelle."""
import os
from datetime import datetime, timezone

import httpx
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

from commun.modeles import Ecosysteme, Etat, Version
from plateforme.db.acces import Base
from plateforme.pipeline import pypi

MAX_PAQUETS = 100  # un paquet et toutes ses dépendances ; au-delà, on refuse plutôt que d'inonder


def _resoudre(client: httpx.Client, nom: str, specifier: SpecifierSet | None,
              maintenant: datetime, choisies: dict[str, Version]) -> None:
    """Ajoute à `choisies` la version mûre de `nom` puis, récursivement, ses dépendances."""
    nom = canonicalize_name(nom)
    if nom in choisies:  # déjà vu : cycle ou dépendance commune
        return
    if len(choisies) >= MAX_PAQUETS:
        raise ValueError(f"plus de {MAX_PAQUETS} paquets avec les dépendances : demande refusée")
    choix = pypi.derniere_version_mure(nom, maintenant, specifier=specifier, client=client)
    if choix is None:
        contrainte = f" {specifier}" if specifier else ""
        raise LookupError(f"{nom}{contrainte} : aucune version publiée depuis plus de "
                          f"{pypi.DELAI.days} jours")
    version, publiee_le = choix
    choisies[nom] = Version(ecosysteme=Ecosysteme.PYPI, nom=nom, version=version,
                            publiee_le=publiee_le, detectee_le=maintenant, etat=Etat.EN_ATTENTE)
    for dep in pypi.dependances(nom, version, client=client):
        _resoudre(client, dep.name, dep.specifier or None, maintenant, choisies)


def demander(ecosysteme: Ecosysteme | str, nom: str, *, maintenant: datetime | None = None,
             base: Base | None = None) -> Version:
    """Enregistre en attente la dernière version mûre de `nom` et de chacune de ses dépendances.

    Chaque dépendance suit le même parcours (délai, analyse) qu'un paquet demandé : rien n'arrive
    sur les serveurs sans être vérifié. Tout est résolu avant d'écrire : si une dépendance manque,
    rien n'est enregistré. Le web appelle `demander(eco, nom)` sans base : on prend alors SAS_DB.

    Lève LookupError (paquet ou dépendance introuvable, ou trop récent), ValueError (nom invalide,
    trop de dépendances), NotImplementedError (npm, extension du MVP).
    """
    if Ecosysteme(ecosysteme) is not Ecosysteme.PYPI:
        raise NotImplementedError("npm est une extension du MVP")
    maintenant = maintenant or datetime.now(timezone.utc)
    choisies: dict[str, Version] = {}
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        _resoudre(client, nom, None, maintenant, choisies)
    base = base or Base(os.environ.get("SAS_DB", "sas.db"))
    for v in choisies.values():
        base.enregistrer_version(v)
    return choisies[canonicalize_name(nom)]
