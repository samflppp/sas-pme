"""Récepteur de la passerelle, sur :8443 (docs/contrats.md § 4).

N'écrit dans le dépôt de pypiserver qu'une publication signée par la plateforme, dont chaque hash
correspond. Le TLS mutuel (certificat client de la plateforme exigé) est posé par uvicorn :
  uvicorn passerelle.recepteur:app --host 0.0.0.0 --port 8443 \
    --ssl-keyfile … --ssl-certfile … --ssl-ca-certs ca.pem --ssl-cert-reqs 2

Configuration de `app` (variables d'environnement) :
  SAS_DEPOT          dossier servi par pypiserver (défaut /srv/pypi/packages)
  SAS_CLE_PUBLIQUE   clé publique Ed25519 de la plateforme, en PEM (posée à l'installation)
  SAS_NONCES         fichier des nonces déjà vus (défaut /var/lib/sas/nonces.txt)
  SAS_JOURNAL_ACCES  journal d'accès de pypiserver, lu par /v1/inventory (défaut
                     /var/lib/sas/pypiserver-acces.log ; inventaire vide si absent)
"""

import os
import re
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from passerelle.inventaire import inventaire as _inventaire
from passerelle.inventaire import meme_version
from passerelle.verification import Refus, verifier

_NOM_SUR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def creer_app(depot: Path, cle_publique_pem: bytes, fichier_nonces: Path,
              horloge: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
              journal_acces: Path | None = None, registre: Path | None = None) -> FastAPI:
    depot, fichier_nonces = Path(depot), Path(fichier_nonces)
    journal_acces = Path(journal_acces) if journal_acces is not None else None
    registre = Path(registre) if registre is not None else None

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
        return {"pypi": depot.is_dir(), "npm": False}

    @app.get("/v1/inventory")
    def inventaire():
        # Contrat § 4 (sens précisé par la PR #38) : chaque version du dépôt, plus les révoquées
        # déjà téléchargées. `machines` (les IP des serveurs) est hors `EntreeInventaire`, joint au
        # JSON brut (option b) ; la plateforme l'ignore (lire_inventaire).
        fichiers = [p.name for p in depot.iterdir() if p.is_file() and not p.name.startswith(".")]
        return [{**e.model_dump(mode="json"), "machines": m}
                for e, m in _inventaire(_lire(journal_acces), fichiers, _lire(registre))]

    @app.post("/v1/publish", status_code=201)
    def publier(manifeste: str = Form(), signature: str = Form(),
                archives: list[UploadFile] = []):
        recues = {a.filename or "": a.file.read() for a in archives}
        with verrou:
            m = _verifier(manifeste, signature, recues, "publication")
            for nom, contenu in recues.items():
                provisoire = depot / f".{nom}.part"
                provisoire.write_bytes(contenu)
                os.replace(provisoire, depot / nom)
            _noter("publie", list(recues))
        return {"publie": [f.nom for f in m.fichiers]}

    @app.post("/v1/revoke")
    def revoquer(manifeste: str = Form(), signature: str = Form()):
        with verrou:
            m = _verifier(manifeste, signature, {}, "revocation")
            if not (_NOM_SUR.match(m.nom) and _NOM_SUR.match(m.version)):
                raise HTTPException(400, "nom ou version interdit")
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


def _depuis_env() -> FastAPI:
    return creer_app(Path(os.environ.get("SAS_DEPOT", "/srv/pypi/packages")),
                     Path(os.environ["SAS_CLE_PUBLIQUE"]).read_bytes(),
                     Path(os.environ.get("SAS_NONCES", "/var/lib/sas/nonces.txt")),
                     journal_acces=Path(os.environ.get(
                         "SAS_JOURNAL_ACCES", "/var/lib/sas/pypiserver-acces.log")),
                     registre=Path(os.environ.get("SAS_REGISTRE", "/var/lib/sas/registre.txt")))


def __getattr__(nom: str):                # `uvicorn passerelle.recepteur:app`, sans effet à l'import
    if nom == "app":
        return _depuis_env()
    raise AttributeError(nom)
