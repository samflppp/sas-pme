"""Documents du RAG : les avis OSV de PyPI et un petit référentiel CWE / CAPEC / ATT&CK.

- **L'export OSV de PyPI** (`osv-vulnerabilities.storage.googleapis.com/PyPI/all.zip`) réunit les
  paquets malveillants d'OpenSSF (`MAL-…`), les avis GitHub (`GHSA-…`) et ceux de la PyPA
  (`PYSEC-…`). Un même avis a souvent deux identifiants (alias) : il n'est indexé qu'une fois.
- **Le référentiel** (`donnees/referentiel_rag.json`) : les faiblesses, attaques et techniques de
  la chaîne d'approvisionnement, résumées en français, avec le nom officiel et le lien.

Ce sont des **données** : leur texte est encadré par `<donnee>` dans le prompt, jamais suivi.
"""
import json
import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

TAILLE_DOCUMENT = 1200
REFERENTIEL = Path(__file__).resolve().parents[1] / "donnees" / "referentiel_rag.json"
_SOURCES = {"MAL": "openssf", "GHSA": "ghsa", "PYSEC": "osv"}
_PRIORITE = {"MAL": 0, "GHSA": 1, "PYSEC": 2}
_BRUIT = re.compile(r"^(---|_-= Per source details.*|## Source: .*)$", re.MULTILINE)


@dataclass(frozen=True)
class Document:
    ref: str
    source: str
    texte: str


def _prefixe(ref: str) -> str:
    return ref.split("-", 1)[0]


def _cwes(avis: dict) -> list[str]:
    noms = {}
    for a in avis.get("affected", []):
        for c in (a.get("database_specific") or {}).get("cwes", []):
            noms[c["cweId"]] = c.get("name", "")
    for c in (avis.get("database_specific") or {}).get("cwe_ids", []):
        noms.setdefault(c, "")
    return [f"{c} ({n})" if n else c for c, n in noms.items()]


def depuis_osv(avis: dict) -> Document | None:
    if avis.get("withdrawn"):
        return None
    ref = avis["id"]
    paquets = sorted({a["package"]["name"] for a in avis.get("affected", []) if "package" in a})
    details = re.sub(r"\s+", " ", _BRUIT.sub("", avis.get("details", ""))).strip()
    cwes = _cwes(avis)
    if not details and not cwes:
        return None   # « Malicious code in X » seul : rien qu'un passage puisse expliquer
    lignes = [f"{ref} — {avis.get('summary') or 'sans résumé'}",
              f"Paquets PyPI : {', '.join(paquets) or '?'}"]
    if avis.get("aliases"):
        lignes.append(f"Alias : {', '.join(avis['aliases'])}")
    if cwes:
        lignes.append(f"Faiblesses : {', '.join(cwes)}")
    lignes.append(details)
    texte = "\n".join(lignes)
    if len(texte) > TAILLE_DOCUMENT:
        texte = texte[:TAILLE_DOCUMENT - 1] + "…"
    return Document(ref, _SOURCES.get(_prefixe(ref), "osv"), texte)


def lire_osv(chemin: Path, *, malveillants_seuls: bool = False) -> Iterator[Document]:
    """Les documents de l'export OSV ; MAL d'abord, puis GHSA, puis PYSEC (alias écartés)."""
    with zipfile.ZipFile(chemin) as z:
        noms = sorted((n for n in z.namelist() if n.endswith(".json")),
                      key=lambda n: (_PRIORITE.get(_prefixe(Path(n).stem), 3), n))
        if malveillants_seuls:
            noms = [n for n in noms if _prefixe(Path(n).stem) == "MAL"]
        vus: set[str] = set()
        for n in noms:
            avis = json.loads(z.read(n))
            if avis["id"] in vus:
                continue
            vus.update([avis["id"], *avis.get("aliases", [])])
            if d := depuis_osv(avis):
                yield d


def referentiel() -> list[Document]:
    entrees = json.loads(REFERENTIEL.read_text(encoding="utf-8"))["documents"]
    return [Document(e["ref"], e["source"],
                     f"{e['ref']} — {e['nom']}\n{e['texte']}\nSource : {e['url']}")
            for e in entrees]
