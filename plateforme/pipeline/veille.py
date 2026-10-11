"""Veille (M1) : à chaque tour, lit PyPI, le registre npm et OSV pour les paquets suivis.

- Une nouvelle version d'un paquet déjà au catalogue entre en attente (le délai part de sa
  publication sur PyPI) : c'est ainsi que les mises à jour arrivent dans la file.
- Une version en attente retirée de PyPI (« yanked », sans fichier, paquet supprimé) ou de npm
  (dépréciée, dépubliée, paquet supprimé) est bloquée : c'est tout l'intérêt du délai.
- Une version en attente connue malveillante par OSV (identifiant MAL-…) est bloquée.

Seules des sources structurées (API de PyPI et d'OSV) bloquent ici ; un article ne bloque jamais
(commun/modeles.py). Ne sortent vers Internet que des noms de paquets et des versions. Une source
injoignable ne bloque rien et ne casse pas le tour : on réessaie au suivant.
"""
import os
import sys
from datetime import datetime

import httpx
from packaging.version import InvalidVersion, Version as VersionPep440

from commun.modeles import Ecosysteme, Etat, Niveau, Signal, Source, Version
from plateforme.db.acces import Base
from plateforme.pipeline import npm, politique, pypi, semver

OSV = os.environ.get("SAS_OSV_URL", "https://api.osv.dev")
P = Ecosysteme.PYPI
_OSV_ECOSYSTEME = {Ecosysteme.PYPI: "PyPI", Ecosysteme.NPM: "npm"}


def _pep(v: str) -> VersionPep440 | None:
    try:
        return VersionPep440(v)
    except InvalidVersion:
        return None


def _bloquer(base: Base, v: Version, sorte: str, preuve: dict) -> Signal:
    s = Signal(ecosysteme=v.ecosysteme, nom=v.nom, version=v.version, source=Source.VEILLE,
               niveau=Niveau.BLOQUANT, sorte=sorte, preuve=preuve)
    base.ajouter_signal(s)
    verdict = politique.decider([s])
    base.enregistrer_verdict(v.ecosysteme, v.nom, v.version, verdict, acteur="veille")
    base.changer_etat(v.ecosysteme, v.nom, v.version, verdict.etat, verdict.raison,
                      acteur="veille")
    return s


def _ordre(eco: Ecosysteme, version: str):
    """Clé de comparaison des versions : PEP 440 pour PyPI, semver pour npm ; None si illisible."""
    if eco is Ecosysteme.NPM:
        return semver.cle(version) if semver.lire(version) else None
    return _pep(version)


def _suivre(base: Base, eco: Ecosysteme, nom: str, connues: list[Version], maintenant: datetime,
            *, client: httpx.Client, url: str
            ) -> tuple[list[Version], list[tuple[Version, Signal]]]:
    registre, nom_registre = (npm, "npm") if eco is Ecosysteme.NPM else (pypi, "PyPI")
    try:
        publiees = dict(registre.versions_publiees(nom, client=client, base=url))
    except LookupError:
        publiees = {}  # paquet supprimé du registre
    nouvelles, bloquees = [], []
    for v in connues:
        if v.etat is Etat.EN_ATTENTE and v.version not in publiees:
            lien = (f"https://www.npmjs.com/package/{nom}/v/{v.version}" if eco is Ecosysteme.NPM
                    else f"{url}/project/{nom}/{v.version}/")
            preuve = {"extrait": f"{nom} {v.version} a été retirée de {nom_registre} pendant "
                                 "l'attente", "url": lien}
            sorte = "retiree_npm" if eco is Ecosysteme.NPM else "retiree_pypi"
            bloquees.append((v, _bloquer(base, v, sorte, preuve)))
    plus_haute = max(filter(None, (_ordre(eco, v.version) for v in connues)), default=None)
    candidates = [(o, ver, d) for ver, d in publiees.items()
                  if (o := _ordre(eco, ver)) and (plus_haute is None or o > plus_haute)]
    if candidates:
        _, ver, publiee_le = max(candidates)
        v = Version(ecosysteme=eco, nom=nom, version=ver, publiee_le=publiee_le,
                    detectee_le=maintenant, etat=Etat.EN_ATTENTE)
        if base.enregistrer_version(v, acteur="veille"):
            nouvelles.append(v)
    return nouvelles, bloquees


def _osv(base: Base, *, client: httpx.Client, osv_url: str) -> list[tuple[Version, Signal]]:
    attente = [v for v in base.lister_versions(Etat.EN_ATTENTE) if v.ecosysteme in _OSV_ECOSYSTEME]
    if not attente:
        return []
    r = client.post(f"{osv_url}/v1/querybatch", json={"queries": [
        {"package": {"name": v.nom, "ecosystem": _OSV_ECOSYSTEME[v.ecosysteme]},
         "version": v.version} for v in attente]})
    r.raise_for_status()
    bloquees = []
    for v, resultat in zip(attente, r.json()["results"], strict=True):
        mal = sorted(x["id"] for x in resultat.get("vulns") or [] if x["id"].startswith("MAL-"))
        if mal:
            preuve = {"extrait": f"OSV : {mal[0]}, paquet malveillant connu", "ref": mal[0],
                      "url": f"https://osv.dev/vulnerability/{mal[0]}"}
            bloquees.append((v, _bloquer(base, v, "malveillant_osv", preuve)))
    return bloquees


def veiller(base: Base, maintenant: datetime, *, client: httpx.Client,
            pypi_url: str = pypi.BASE, npm_url: str = npm.BASE, osv_url: str = OSV
            ) -> tuple[list[Version], list[tuple[Version, Signal]]]:
    """Un tour de veille ; renvoie (nouvelles versions en attente, versions bloquées + signal)."""
    par_nom: dict[tuple[Ecosysteme, str], list[Version]] = {}
    for v in base.lister_versions():
        if v.ecosysteme in _OSV_ECOSYSTEME:
            par_nom.setdefault((v.ecosysteme, v.nom), []).append(v)
    nouvelles, bloquees = [], []
    for (eco, nom), connues in sorted(par_nom.items()):
        url = npm_url if eco is Ecosysteme.NPM else pypi_url
        try:
            n, b = _suivre(base, eco, nom, connues, maintenant, client=client, url=url)
        except (httpx.HTTPError, ValueError, KeyError) as e:
            print(f"[sas-pme] veille {eco.value} {nom} : {e!r}", file=sys.stderr)
            continue
        nouvelles += n
        bloquees += b
    try:
        bloquees += _osv(base, client=client, osv_url=osv_url)
    except (httpx.HTTPError, ValueError, KeyError) as e:
        print(f"[sas-pme] veille OSV : {e!r}", file=sys.stderr)
    return nouvelles, bloquees
