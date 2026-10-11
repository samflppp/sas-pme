"""Récepteur de la passerelle, sur :8443 (docs/contrats.md § 4).

N'écrit dans le dépôt de pypiserver (pip) ou dans Verdaccio (npm, sans source amont) qu'une
publication signée par la plateforme, dont chaque hash correspond. Le TLS mutuel (certificat client de la plateforme exigé) est posé par uvicorn :
  uvicorn passerelle.recepteur:app --host 0.0.0.0 --port 8443 \
    --ssl-keyfile … --ssl-certfile … --ssl-ca-certs ca.pem --ssl-cert-reqs 2

Configuration de `app` (variables d'environnement) :
  SAS_DEPOT          dossier servi par pypiserver (défaut /srv/pypi/packages)
  SAS_CLE_PUBLIQUE   clé publique Ed25519 de la plateforme, en PEM (posée à l'installation)
  SAS_NONCES         fichier des nonces déjà vus (défaut /var/lib/sas/nonces.txt)
  SAS_JOURNAL_ACCES  journal d'accès de pypiserver, lu par /v1/inventory et /v1/access (défaut
                     /var/lib/sas/pypiserver-acces.log ; inventaire vide si absent)
  SAS_VERDACCIO_URL  Verdaccio de la passerelle (défaut http://127.0.0.1:4873)
  SAS_VERDACCIO_JETON fichier du jeton de publication de Verdaccio (défaut
                     /var/lib/sas-recepteur/verdaccio.jeton) ; absent : npm refusé (503)
  SAS_JOURNAL_NPM    journal JSON de Verdaccio, lu par /v1/inventory (défaut /var/lib/sas/verdaccio.log)
  SAS_INSTALLATIONS  demandes d'installation signées reçues par /v1/install, une par ligne
                     (défaut /var/lib/sas/installations.jsonl), servies aux serveurs par le guichet
                     (`passerelle.guichet`, :8444)
"""

import json
import os
import re
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from passerelle import installation
from passerelle.acces import requetes
from passerelle.inventaire import inventaire as _inventaire
from passerelle.inventaire import meme_version
from passerelle.inventaire_npm import PREFIXE as _NPM
from passerelle.inventaire_npm import inventaire as _inventaire_npm
from passerelle.verification import Refus, verifier

_NOM_SUR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_NOM_NPM = re.compile(r"^(@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]{0,213}$")


def _nom_sur(ecosysteme: str, nom: str, version: str) -> bool:
    if ".." in nom or not _NOM_SUR.match(version):
        return False
    return bool((_NOM_NPM if ecosysteme == "npm" else _NOM_SUR).match(nom))


def creer_app(depot: Path, cle_publique_pem: bytes, fichier_nonces: Path,
              horloge: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
              journal_acces: Path | None = None, registre: Path | None = None,
              installations: Path | None = None, depot_npm=None,
              journal_npm: Path | None = None) -> FastAPI:
    """`depot_npm` : le Verdaccio de la passerelle (`passerelle.verdaccio.Verdaccio`), ou None."""
    depot, fichier_nonces = Path(depot), Path(fichier_nonces)
    installations = Path(installations) if installations is not None else None
    journal_acces = Path(journal_acces) if journal_acces is not None else None
    registre = Path(registre) if registre is not None else None
    journal_npm = Path(journal_npm) if journal_npm is not None else None

    def _noter(action: str, archives: list[str]) -> None:
        """Registre des archives écrites ou retirées, lu par l'inventaire (PR #38)."""
        if registre is not None and archives:
            quand = horloge().isoformat()
            with registre.open("a") as f:
                f.writelines(f"{quand} {action} {a}\n" for a in archives)

    def _lire(chemin: Path | None) -> list[str]:
        if chemin is None or not chemin.exists():
            return []
        return chemin.read_text(encoding="utf-8", errors="replace").splitlines()
    nonces = set(fichier_nonces.read_text().split()) if fichier_nonces.exists() else set()
    verrou = threading.Lock()          # vérification + écriture d'une publication à la fois
    app = FastAPI(title="sas-pme passerelle", docs_url=None, redoc_url=None, openapi_url=None)

    def _verifier(manifeste: str, signature: str, archives: dict[str, bytes], type_attendu: str):
        try:
            m = verifier(manifeste.encode(), signature, archives, cle_publique_pem, horloge(),
                         nonces)
        except Refus as e:
            raise HTTPException(e.code, str(e)) from e
        if m.type != type_attendu:
            nonces.discard(m.nonce)
            raise HTTPException(400, f"manifeste de type {m.type}, attendu {type_attendu}")
        with fichier_nonces.open("a") as f:
            f.write(m.nonce + "\n")
        return m

    @app.get("/v1/health")
    def sante():
        return {"pypi": depot.is_dir(), "npm": depot_npm is not None and depot_npm.disponible()}

    @app.get("/v1/inventory")
    def inventaire():
        # Contrat § 4 (sens précisé par la PR #38) : chaque version du dépôt, plus les révoquées
        # déjà téléchargées. `machines` (les IP des serveurs) est hors `EntreeInventaire`, joint au
        # JSON brut (option b) ; la plateforme l'ignore (lire_inventaire).
        fichiers = [p.name for p in depot.iterdir() if p.is_file() and not p.name.startswith(".")]
        entrees = [*_inventaire(_lire(journal_acces), fichiers, _lire(registre)),
                   *_inventaire_npm(_lire(journal_npm), _lire(registre))]
        entrees.sort(key=lambda em: (em[0].ecosysteme.value, em[0].nom, em[0].version))
        return [{**e.model_dump(mode="json"), "machines": m} for e, m in entrees]

    @app.post("/v1/publish", status_code=201)
    def publier(manifeste: str = Form(), signature: str = Form(),
                archives: list[UploadFile] = []):
        recues = {a.filename or "": a.file.read() for a in archives}
        if _ecosysteme(manifeste) == "npm" and depot_npm is None:
            # Avant toute vérification : le nonce n'est pas consommé, la publication pourra revenir.
            raise HTTPException(503, "aucun dépôt npm (Verdaccio) configuré sur cette passerelle")
        with verrou:
            m = _verifier(manifeste, signature, recues, "publication")
            if m.ecosysteme.value == "npm":
                if not _nom_sur("npm", m.nom, m.version):
                    raise HTTPException(400, "nom ou version interdit")
                try:
                    for nom, contenu in recues.items():
                        depot_npm.publier(m.nom, m.version, nom, contenu)
                except Exception as e:  # noqa: BLE001 — refus de Verdaccio : rien n'est noté
                    raise HTTPException(502, f"dépôt npm : {e}") from e
                _noter("publie", [f"{_NPM}{m.nom}@{m.version}"])
                return {"publie": [f.nom for f in m.fichiers]}
            for nom, contenu in recues.items():
                provisoire = depot / f".{nom}.part"
                provisoire.write_bytes(contenu)
                os.replace(provisoire, depot / nom)
            _noter("publie", list(recues))
        return {"publie": [f.nom for f in m.fichiers]}

    @app.get("/v1/access")
    def acces(apres: int = 0):
        """Les requêtes des serveurs à pypiserver après la ligne `apres` (panneau « Serveur »)."""
        lignes = _lire(journal_acces)
        return {"total": len(lignes), "lignes": requetes(lignes, apres)}

    @app.post("/v1/install", status_code=201)
    def installer(demande: str = Form(), signature: str = Form()):
        """Une demande d'installation signée par la plateforme, rangée pour le guichet ; le serveur
        la vérifie à nouveau avant de lancer pip (passerelle.installation)."""
        if installations is None:
            raise HTTPException(503, "aucun fichier de demandes d'installation configuré")
        with verrou:
            try:
                d = installation.verifier(demande, signature, cle_publique_pem, horloge(), nonces)
            except Refus as e:
                raise HTTPException(e.code, str(e)) from e
            with fichier_nonces.open("a") as f:
                f.write(d.nonce + "\n")
            n = len(_lire(installations)) + 1
            with installations.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"n": n, "demande": demande, "signature": signature}) + "\n")
        return {"n": n, "nom": d.nom}

    @app.post("/v1/revoke")
    def revoquer(manifeste: str = Form(), signature: str = Form()):
        with verrou:
            m = _verifier(manifeste, signature, {}, "revocation")
            if not _nom_sur(m.ecosysteme.value, m.nom, m.version):
                raise HTTPException(400, "nom ou version interdit")
            if m.ecosysteme.value == "npm":
                if depot_npm is None:
                    raise HTTPException(503, "aucun dépôt npm (Verdaccio) configuré")
                retires = depot_npm.retirer(m.nom, m.version)
                if retires:
                    _noter("retire", [f"{_NPM}{m.nom}@{m.version}"])
                return JSONResponse({"retire": retires})
            # Même règle de noms que l'inventaire (PEP 503 / PEP 440). Rien à retirer → 200 quand
            # même : la version est absente, c'est l'état voulu (sinon l'admin ne peut plus la
            # marquer révoquée) ; `retire: []` le dit.
            retires = [p.name for p in depot.iterdir()
                       if p.is_file() and meme_version(p.name, m.nom, m.version)]
            for nom in retires:
                (depot / nom).unlink()
            _noter("retire", retires)
        return JSONResponse({"retire": retires})

    return app


def _ecosysteme(manifeste: str) -> str:
    """L'écosystème annoncé, pour router avant la vérification (qui le confirme ensuite)."""
    try:
        return str(json.loads(manifeste).get("ecosysteme", ""))
    except (ValueError, AttributeError):
        return ""


def _verdaccio_depuis_env():
    chemin = Path(os.environ.get("SAS_VERDACCIO_JETON", "/var/lib/sas-recepteur/verdaccio.jeton"))
    jeton = chemin.read_text().strip() if chemin.is_file() else ""
    if not jeton:                       # absent ou vide : pas de npm (503), jamais « Bearer  »
        return None
    from passerelle.verdaccio import Verdaccio
    return Verdaccio(os.environ.get("SAS_VERDACCIO_URL", "http://127.0.0.1:4873"), jeton)


def _depuis_env() -> FastAPI:
    return creer_app(Path(os.environ.get("SAS_DEPOT", "/srv/pypi/packages")),
                     Path(os.environ["SAS_CLE_PUBLIQUE"]).read_bytes(),
                     Path(os.environ.get("SAS_NONCES", "/var/lib/sas/nonces.txt")),
                     journal_acces=Path(os.environ.get(
                         "SAS_JOURNAL_ACCES", "/var/lib/sas/pypiserver-acces.log")),
                     registre=Path(os.environ.get("SAS_REGISTRE", "/var/lib/sas/registre.txt")),
                     installations=Path(os.environ.get(
                         "SAS_INSTALLATIONS", "/var/lib/sas/installations.jsonl")),
                     depot_npm=_verdaccio_depuis_env(),
                     journal_npm=Path(os.environ.get("SAS_JOURNAL_NPM",
                                                     "/var/lib/sas/verdaccio.log")))


def __getattr__(nom: str):                # `uvicorn passerelle.recepteur:app`, sans effet à l'import
    if nom == "app":
        return _depuis_env()
    raise AttributeError(nom)
