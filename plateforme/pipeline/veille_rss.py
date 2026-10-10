"""Veille par flux RSS (M2) : les blogs de chercheurs, lus à chaque tour de veille.

- Un article **alerte** quand il emploie un mot d'attaque (malicious, compromised, backdoor…) et
  nomme un paquet du catalogue. S'il cite une version (« demo-horodatage 1.2 »), c'est elle qui
  est visée ; sinon, s'il parle de PyPI, seules les versions **en attente** du paquet le sont.
- L'alerte est un signal `VEILLE` **non structuré**, de niveau FORT : le type refuse qu'un article
  bloque (commun/modeles.py), et rien dans la politique ne laisse un article approuver. Un article
  ne débloque donc jamais rien, même s'il le demande.
- Effet : en attente ou en analyse, le signal entre dans la politique à l'analyse (à revoir) ;
  approuvée pas encore publiée, la version repasse à revoir ; publiée, le signal et le journal
  préviennent l'humain, qui décide de révoquer. Pas de révocation sur un simple article.
- Les flux : `SAS_FLUX` (URL séparées par des virgules), sinon `donnees/flux_rss.txt`. Chaque flux
  est relu au plus toutes les `PERIODE_MIN` minutes. Un flux injoignable est ignoré ce tour-ci.
"""
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import feedparser
import httpx

from commun.modeles import Ecosysteme, Etat, Niveau, Signal, Source, Version
from plateforme.db.acces import Base

PERIODE_MIN = 30
FLUX_DEFAUT = Path(__file__).resolve().parent / "donnees" / "flux_rss.txt"
EXTRAIT_MAX = 200
_ATTAQUE = re.compile(r"\b(malicious|malware|compromi[sz]|backdoor|typosquat|steal|trojan|"
                      r"hijack|exfiltrat|worm|malveillant|piég)", re.IGNORECASE)
_BALISE = re.compile(r"<[^>]+>")
_VISEES = {Etat.NOUVELLE, Etat.EN_ATTENTE, Etat.EN_ANALYSE, Etat.A_REVOIR, Etat.APPROUVEE,
           Etat.PUBLIEE}
_dernier_passage: dict[str, datetime] = {}


def flux() -> list[str]:
    brut = os.environ.get("SAS_FLUX", "").strip()
    lignes = brut.split(",") if brut else FLUX_DEFAUT.read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lignes if l.strip() and not l.strip().startswith("#")]


def _motif_nom(nom: str) -> str:
    """Le nom en mot entier, « - », « _ » et « . » interchangeables (noms PyPI normalisés)."""
    parties = re.split(r"[-_.]+", nom)
    return r"(?<![\w.-])" + r"[-_.]".join(map(re.escape, parties)) + r"(?![\w-])"


def _versions_citees(texte: str, nom: str) -> set[str] | None:
    """Versions citées pour ce nom ; None si le nom n'apparaît pas."""
    motif = _motif_nom(nom)
    if not re.search(motif, texte, re.IGNORECASE):
        return None
    return {m.group(1) for m in re.finditer(
        motif + r"(?:==|@|\s+version\s+v?|\s+v?)(\d+(?:\.\d+)*(?:[a-z]+\d*)?)",
        texte, re.IGNORECASE)}


def _texte(article) -> str:
    morceaux = [article.get("title", ""), article.get("summary", "")]
    morceaux += [c.get("value", "") for c in article.get("content", [])]
    return re.sub(r"\s+", " ", _BALISE.sub(" ", " ".join(morceaux)))


def _alerter(base: Base, v: Version, titre: str, url: str) -> Signal | None:
    cle = (v.ecosysteme, v.nom, v.version)
    if any(s.source is Source.VEILLE and s.preuve.get("url") == url
           for s in base.fiche(*cle).signaux):
        return None
    s = Signal(ecosysteme=v.ecosysteme, nom=v.nom, version=v.version, source=Source.VEILLE,
               niveau=Niveau.FORT, sorte="article", structure=False,
               preuve={"extrait": f"article : {titre}"[:EXTRAIT_MAX], "url": url})
    base.ajouter_signal(s)
    if v.etat is Etat.APPROUVEE:
        base.changer_etat(*cle, Etat.A_REVOIR, f"À revoir : {s.preuve['extrait']} ({url})",
                          acteur="veille")
    elif v.etat is Etat.PUBLIEE:
        base.journaliser("veille", "article_version_publiee",
                         f"{v.ecosysteme.value}/{v.nom}/{v.version}", {"titre": titre[:300],
                                                                        "url": url})
    return s


def _lire(client: httpx.Client, url: str) -> list:
    r = client.get(url)
    r.raise_for_status()
    return feedparser.parse(r.content).entries


def veiller_articles(base: Base, maintenant: datetime, *, client: httpx.Client,
                     flux: list[str], etat: dict[str, datetime] | None = None
                     ) -> list[tuple[Version, Signal]]:
    etat = _dernier_passage if etat is None else etat
    par_nom: dict[str, list[Version]] = {}
    for v in base.lister_versions():
        if v.ecosysteme is Ecosysteme.PYPI and v.etat in _VISEES:
            par_nom.setdefault(v.nom, []).append(v)
    alertes = []
    for url_flux in flux:
        if url_flux in etat and maintenant - etat[url_flux] < timedelta(minutes=PERIODE_MIN):
            continue
        try:
            articles = _lire(client, url_flux)
        except httpx.HTTPError as e:
            print(f"[sas-pme] veille RSS {url_flux} : {e!r}", file=sys.stderr)
            continue
        etat[url_flux] = maintenant
        for article in articles:
            texte = _texte(article)
            if not _ATTAQUE.search(texte):
                continue
            titre, lien = article.get("title", "").strip(), article.get("link", url_flux)
            for nom, versions in par_nom.items():
                citees = _versions_citees(texte, nom)
                if citees is None:
                    continue
                if citees:
                    visees = [v for v in versions if v.version in citees]
                elif re.search(r"\bpypi\b", texte, re.IGNORECASE):
                    visees = [v for v in versions if v.etat in (Etat.NOUVELLE, Etat.EN_ATTENTE)]
                else:
                    visees = []
                for v in visees:
                    if s := _alerter(base, v, titre, lien):
                        alertes.append((v, s))
    return alertes
