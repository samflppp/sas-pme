"""Catalogue en arborescence (A, conception-demo § 1) : ce que la page affiche, sans HTML.

Un paquet, ses versions (de la plus récente à la plus ancienne, au sens PEP 440), la version que
reçoivent les serveurs (la plus récente publiée) et celle qui la suit sans être publiée. Une version,
ses fichiers : les archives téléchargées par la pipeline, et ce que la plateforme sait d'elle
(verdict, rapport de sandbox, signaux), rendus en JSON comme les fichiers d'un dépôt.
Les images Docker ne passent par aucune pipeline : elles viennent d'un fichier tenu à la main.
"""
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from packaging.version import InvalidVersion, Version as VersionPep440

from commun.modeles import Ecosysteme, Etat, Version
from plateforme.db.acces import Fiche


def _cle_pep(v: Version) -> tuple:
    try:
        return (1, VersionPep440(v.version))
    except InvalidVersion:               # une version illisible passe après les autres
        return (0, v.version)


@dataclass(frozen=True)
class Paquet:
    ecosysteme: Ecosysteme
    nom: str
    versions: list[Version]          # la plus récente d'abord
    servie: Version | None           # ce que les serveurs installent aujourd'hui
    suivante: Version | None         # plus récente que la servie, pas (encore) publiée
    derniere_activite: datetime


def _paquet(eco: Ecosysteme, nom: str, versions: list[Version]) -> Paquet:
    tri = sorted(versions, key=_cle_pep, reverse=True)
    servie = next((v for v in tri if v.etat is Etat.PUBLIEE), None)
    plus_recentes = tri[:tri.index(servie)] if servie else tri
    suivante = plus_recentes[-1] if plus_recentes else None
    return Paquet(eco, nom, tri, servie, suivante, max(v.detectee_le for v in versions))


def paquets(versions: list[Version], eco: Ecosysteme) -> list[Paquet]:
    par_nom: dict[str, list[Version]] = {}
    for v in versions:
        if v.ecosysteme is eco:
            par_nom.setdefault(v.nom, []).append(v)
    return [_paquet(eco, nom, vs) for nom, vs in sorted(par_nom.items())]


def paquet(versions: list[Version], eco: Ecosysteme, nom: str) -> Paquet | None:
    vs = [v for v in versions if v.ecosysteme is eco and v.nom == nom]
    return _paquet(eco, nom, vs) if vs else None


# --- fichiers d'une version -------------------------------------------------------------------
@dataclass(frozen=True)
class Fichier:
    nom: str
    sorte: str                        # « archive » (sur disque) ou « donnees » (de la base)
    taille: int
    empreinte: str | None = None      # sha256 d'une archive
    contenu: str | None = None        # JSON d'un fichier de données


def taille_lisible(octets: int) -> str:
    if octets < 1024:
        return f"{octets} o"
    if octets < 1024 * 1024:
        return f"{octets / 1024:.1f} Ko".replace(".", ",")
    return f"{octets / 1024 / 1024:.1f} Mo".replace(".", ",")


def _json(objet) -> str:
    return json.dumps(objet, ensure_ascii=False, indent=2, default=str)


def fichiers_version(fiche: Fiche, archives: Path | None) -> list[Fichier]:
    """Les archives du dossier de la pipeline (`archives/<nom>/<version>/`, B) puis les données.
    Le dossier est construit à partir de la base, jamais de l'URL."""
    v = fiche.version
    sortie: list[Fichier] = []
    dossier = archives / v.nom / v.version if archives is not None else None
    if dossier is not None and dossier.is_dir():
        for f in sorted(p for p in dossier.iterdir() if p.is_file()):
            donnees = f.read_bytes()
            sortie.append(Fichier(f.name, "archive", len(donnees),
                                  empreinte=hashlib.sha256(donnees).hexdigest()))
    donnees = {
        "verdict.json": fiche.verdict.model_dump(mode="json") if fiche.verdict else None,
        "rapport-sandbox.json": (fiche.rapport_sandbox.model_dump(mode="json")
                                 if fiche.rapport_sandbox else None),
        "signaux.json": [s.model_dump(mode="json") for s in fiche.signaux] or None,
    }
    for nom, objet in donnees.items():
        if objet is not None:
            texte = _json(objet)
            sortie.append(Fichier(nom, "donnees", len(texte.encode()), contenu=texte))
    return sortie


# --- images Docker, tenues à la main ----------------------------------------------------------
@dataclass(frozen=True)
class Image:
    nom: str
    tag: str
    source: str
    digest: str
    agreee_le: str
    par: str
    usage: str


def images(chemin: Path | None) -> list[Image]:
    """Absent ou illisible : aucune image (le dossier le dit), jamais une erreur de page."""
    if chemin is None or not chemin.is_file():
        return []
    try:
        brut = json.loads(chemin.read_text(encoding="utf-8"))
        return [Image(**{k: str(e[k]) for k in Image.__dataclass_fields__}) for e in brut]
    except (ValueError, KeyError, TypeError):
        return []
