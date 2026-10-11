"""Inventaire npm de la passerelle : ce que les serveurs ont installé depuis Verdaccio.

Le pendant de `inventaire.py` pour npm. Verdaccio écrit un journal JSON (pino) avec, pour chaque
requête servie, `request.method`, `request.url`, `status`, `remoteIP` et `time` (en ms). Un
téléchargement est un `GET /<nom>/-/<archive>.tgz` répondu 200 ; la page du paquet (`GET /<nom>`)
ne compte pas. Une ligne illisible est ignorée, jamais une erreur.

Entrées (contrat § 4) : chaque version présente dans Verdaccio d'après le registre du récepteur
(« <date> publie|retire npm:<nom>@<version> »), même jamais téléchargée, plus chaque version
téléchargée au moins une fois, même révoquée depuis (un serveur l'a peut-être encore).
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit

from commun.modeles import Ecosysteme, EntreeInventaire

PREFIXE = "npm:"


@dataclass(frozen=True)
class Telechargement:
    nom: str
    version: str
    ip: str
    quand: datetime


def telechargement(ligne: str) -> Telechargement | None:
    try:
        e = json.loads(ligne)
        req = e["request"]
        if req["method"] != "GET" or int(e["status"]) != 200:
            return None
        chemin = unquote(urlsplit(req["url"]).path).lstrip("/")
        nom, archive = chemin.split("/-/", 1)
        base = nom.rsplit("/", 1)[-1] + "-"
        if "/" in archive or not (archive.startswith(base) and archive.endswith(".tgz")):
            return None
        version = archive[len(base):-len(".tgz")]
        quand = datetime.fromtimestamp(int(e["time"]) / 1000, tz=timezone.utc)
        return Telechargement(nom, version, str(e.get("remoteIP") or ""), quand) \
            if nom and version else None
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


def presentes(registre: Iterable[str]) -> set[tuple[str, str]]:
    """(nom, version) publiées et pas retirées depuis, d'après le registre du récepteur."""
    etat: dict[tuple[str, str], tuple[datetime, bool]] = {}
    for ligne in registre:
        morceaux = ligne.split(" ", 2)
        if len(morceaux) != 3 or morceaux[1] not in ("publie", "retire") \
                or not morceaux[2].startswith(PREFIXE):
            continue
        try:
            quand = datetime.fromisoformat(morceaux[0])
        except ValueError:
            continue
        nom, _, version = morceaux[2].strip()[len(PREFIXE):].rpartition("@")
        if not nom or not version:
            continue
        cle = (nom, version)
        if cle not in etat or quand >= etat[cle][0]:
            etat[cle] = (quand, morceaux[1] == "publie")
    return {cle for cle, (_, la) in etat.items() if la}


def inventaire(journal: Iterable[str], registre: Iterable[str]
               ) -> list[tuple[EntreeInventaire, list[str]]]:
    compte: dict[tuple[str, str], int] = {}
    dernier: dict[tuple[str, str], datetime] = {}
    machines: dict[tuple[str, str], list[str]] = {}
    for t in filter(None, map(telechargement, journal)):
        cle = (t.nom, t.version)
        compte[cle] = compte.get(cle, 0) + 1
        dernier[cle] = max(dernier.get(cle, t.quand), t.quand)
        if t.ip and t.ip not in machines.setdefault(cle, []):
            machines[cle].append(t.ip)
    versions = presentes(registre) | set(compte)
    return [(EntreeInventaire(ecosysteme=Ecosysteme.NPM, nom=n, version=v,
                              telechargements=compte.get((n, v), 0), dernier=dernier.get((n, v))),
             machines.get((n, v), []))
            for n, v in sorted(versions)]
