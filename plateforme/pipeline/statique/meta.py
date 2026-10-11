"""Contrôles sur les métadonnées PyPI et npm : âge du projet, changement de mainteneur.

Pour npm, le mainteneur comparé est l'éditeur de la version (`_npmUser`), celui dont le compte a
publié : un compte repris (Shai-Hulud, chalk/debug en 2025) publie sous un autre éditeur.

Des indices (MOYEN), pas des preuves : un projet neuf ou un nouveau mainteneur est souvent
légitime, mais c'est le terrain des typosquats et des comptes repris. Une source injoignable ne
donne aucun signal (la veille et les autres contrôles continuent).
"""
import sys
from datetime import datetime

import httpx

from commun.modeles import Ecosysteme, Niveau, Signal, Source
from plateforme.pipeline import npm, pypi

JOURS_RECENT = 30


def _signal(eco, nom, version, sorte, extrait, **plus) -> Signal:
    return Signal(ecosysteme=eco, nom=nom, version=version, source=Source.STATIQUE,
                  niveau=Niveau.MOYEN, sorte=sorte, preuve={"extrait": extrait, **plus})


def _courriels(nom: str, version: str, client: httpx.Client, base_url: str) -> set[str]:
    r = client.get(f"{base_url}/pypi/{nom}/{version}/json")
    r.raise_for_status()
    info = r.json()["info"]
    return {c.strip().lower() for cle in ("author_email", "maintainer_email")
            for c in (info.get(cle) or "").split(",") if c.strip()}


def _editeur(paquet: dict, version: str) -> set[str]:
    u = ((paquet.get("versions") or {}).get(version) or {}).get("_npmUser") or {}
    return {x.strip().lower() for x in (u.get("email"), u.get("name")) if x and x.strip()}


def _npm(eco: Ecosysteme, nom: str, version: str, precedente: str | None, maintenant: datetime,
         client: httpx.Client, npm_url: str) -> list[Signal]:
    signaux = []
    paquet = npm.metadonnees(nom, client=client, base=npm_url)
    cree = (paquet.get("time") or {}).get("created")
    if cree and (age := (maintenant - datetime.fromisoformat(cree.replace("Z", "+00:00"))).days) \
            < JOURS_RECENT:
        signaux.append(_signal(eco, nom, version, "projet_recent",
                               f"projet publié pour la première fois il y a {age} jours"))
    if precedente:
        avant, apres = _editeur(paquet, precedente), _editeur(paquet, version)
        if avant and apres and not avant & apres:
            signaux.append(_signal(eco, nom, version, "mainteneur_change",
                                   f"éditeur changé depuis {precedente} : "
                                   f"{', '.join(sorted(apres))}", precedente=precedente))
    return signaux


def controler_metadonnees(eco: Ecosysteme, nom: str, version: str, *, precedente: str | None,
                          maintenant: datetime, client: httpx.Client,
                          base_url: str = pypi.BASE, npm_url: str = npm.BASE) -> list[Signal]:
    if eco is Ecosysteme.NPM:
        try:
            return _npm(eco, nom, version, precedente, maintenant, client, npm_url)
        except (httpx.HTTPError, LookupError, ValueError, KeyError) as e:
            print(f"[sas-pme] métadonnées npm {nom} {version} : {e!r}", file=sys.stderr)
            return []
    signaux = []
    try:
        releases = pypi.metadonnees(nom, client=client, base=base_url)["releases"]
        dates = [datetime.fromisoformat(f["upload_time_iso_8601"].replace("Z", "+00:00"))
                 for fichiers in releases.values() for f in fichiers]
        if dates and (age := (maintenant - min(dates)).days) < JOURS_RECENT:
            signaux.append(_signal(eco, nom, version, "projet_recent",
                                   f"projet publié pour la première fois il y a {age} jours"))
        if precedente:
            avant = _courriels(nom, precedente, client, base_url)
            maintenant_ = _courriels(nom, version, client, base_url)
            if avant and maintenant_ and not avant & maintenant_:
                signaux.append(_signal(
                    eco, nom, version, "mainteneur_change",
                    f"mainteneur changé depuis {precedente} : {', '.join(sorted(maintenant_))}",
                    precedente=precedente))
    except (httpx.HTTPError, LookupError, ValueError, KeyError) as e:
        print(f"[sas-pme] métadonnées {nom} {version} : {e!r}", file=sys.stderr)
    return signaux
