"""Construit demo/corpus/corpus.json : 30 versions PyPI malveillantes, 50 mises à jour saines.

Ne télécharge AUCUNE archive et n'exécute aucun échantillon : on lit seulement
les rapports JSON d'OpenSSF malicious-packages (clone local) et les métadonnées
JSON de PyPI.

Usage (Python isolé, rapports passés en argument) :
    git clone --depth 1 --filter=blob:none --sparse \
        https://github.com/ossf/malicious-packages <dossier>/mp
    git -C <dossier>/mp sparse-checkout set osv/malicious/pypi
    python3 -I demo/corpus/construire.py <dossier>/mp/osv/malicious/pypi
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

from packaging.version import InvalidVersion, Version

SORTIE = Path(__file__).with_name("corpus.json")
AGE_MIN_SAIN_J = 30

# Paquets populaires de l'écosystème d'une PME Python (web, données, cloud, outils).
POPULAIRES = [
    "requests", "urllib3", "certifi", "idna", "charset-normalizer",
    "numpy", "pandas", "python-dateutil", "pytz", "six",
    "setuptools", "wheel", "packaging", "pyyaml", "attrs",
    "click", "jinja2", "markupsafe", "flask", "django",
    "fastapi", "pydantic", "starlette", "uvicorn", "httpx",
    "sqlalchemy", "boto3", "botocore", "s3transfer", "cryptography",
    "cffi", "pycparser", "rsa", "pyasn1", "jmespath",
    "typing-extensions", "filelock", "platformdirs", "pytest", "pluggy",
    "rich", "pygments", "tqdm", "protobuf", "aiohttp",
    "multidict", "yarl", "werkzeug", "itsdangerous", "scipy",
]

_CATEGORIE = re.compile(r"Category:\s*([A-Z_]+)")
_CAMPAGNE = re.compile(r"Campaign:\s*(\S+)")


def _resume(details: str) -> str:
    for ligne in details.splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith(("#", "-", "_", "Category:", "Campaign:")):
            return ligne[:200]
    return ""


def extraire_malveillant(osv: dict) -> dict | None:
    """Une entrée du corpus, ou None si le rapport ne vise pas une version exacte."""
    details = osv.get("details", "")
    categorie = _CATEGORIE.search(details)
    if categorie and categorie.group(1) != "MALICIOUS":
        return None
    affectes = [a for a in osv.get("affected", []) if a.get("versions")]
    if len(affectes) != 1:
        return None
    a = affectes[0]
    campagne = _CAMPAGNE.search(details)
    urls = osv.get("database_specific", {}).get("iocs", {}).get("urls", [])
    domaines = sorted({h for h in (urlsplit(u).hostname for u in urls) if h})
    return {
        "ecosysteme": "pypi",
        "nom": a["package"]["name"],
        "version": a["versions"][-1],
        "ref": osv["id"],
        "publie_le": osv.get("published", ""),
        "campagne": campagne.group(1) if campagne else "",
        "resume": _resume(details),
        "domaines_ioc": domaines,
    }


def choisir_malveillants(
    rapports: list[dict], n: int = 30, par_campagne: int = 2, exclus: set[str] = frozenset()
) -> list[dict]:
    """Les n rapports les plus récents, un par paquet, au plus `par_campagne` par campagne."""
    entrees = [e for e in map(extraire_malveillant, rapports) if e]
    entrees.sort(key=lambda e: (e["publie_le"], e["ref"]), reverse=True)
    choix, noms, campagnes = [], set(), {}
    for e in entrees:
        nom = e["nom"].lower()
        cle = e["campagne"] or e["ref"]
        if nom in noms or nom in exclus or campagnes.get(cle, 0) >= par_campagne:
            continue
        choix.append(e)
        noms.add(nom)
        campagnes[cle] = campagnes.get(cle, 0) + 1
        if len(choix) == n:
            break
    return choix


def choisir_sain(nom: str, pypi: dict, limite: datetime | None = None) -> dict | None:
    """La dernière mise à jour stable : (avant-dernière, dernière) version non retirées.

    Avec `limite`, seules comptent les versions publiées avant cette date : une version
    vieille d'au moins 30 jours sans retrait sert de vérité terrain « saine ».
    """
    stables = []
    for brute, fichiers in pypi.get("releases", {}).items():
        if not fichiers or any(f.get("yanked") for f in fichiers):
            continue
        try:
            v = Version(brute)
        except InvalidVersion:
            continue
        if v.is_prerelease or v.is_devrelease:
            continue
        date = min(f["upload_time_iso_8601"] for f in fichiers)
        if limite and datetime.fromisoformat(date.replace("Z", "+00:00")) >= limite:
            continue
        stables.append((v, brute, date))
    if len(stables) < 2:
        return None
    stables.sort()
    (_, avant, _), (_, apres, date) = stables[-2], stables[-1]
    return {
        "ecosysteme": "pypi",
        "nom": pypi.get("info", {}).get("name", nom),
        "version_precedente": avant,
        "version": apres,
        "publiee_le": date,
    }


def _lire_rapports(dossier: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(dossier.glob("*/*.json"))]


def _pypi_json(nom: str) -> dict:
    with urlopen(f"https://pypi.org/pypi/{nom}/json", timeout=30) as r:
        return json.load(r)


def main(dossier_rapports: str) -> None:
    limite = datetime.now(timezone.utc) - timedelta(days=AGE_MIN_SAIN_J)
    sains = [e for e in (choisir_sain(n, _pypi_json(n), limite) for n in POPULAIRES) if e]
    exclus = {e["nom"].lower() for e in sains}
    malveillants = choisir_malveillants(_lire_rapports(Path(dossier_rapports)), exclus=exclus)
    corpus = {
        "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {
            "malveillants": "https://github.com/ossf/malicious-packages (osv/malicious/pypi)",
            "sains": "https://pypi.org/pypi/<nom>/json",
        },
        "avertissement": "Liste de noms et versions seulement. Ne jamais installer un "
        "paquet malveillant hors de la sandbox.",
        "malveillants": malveillants,
        "sains": sains,
    }
    SORTIE.write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(malveillants)} malveillants, {len(sains)} sains -> {SORTIE}")


if __name__ == "__main__":
    main(sys.argv[1])
