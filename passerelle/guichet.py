"""Guichet de la passerelle pour les serveurs (A pour C), sur :8444, réseau privé seulement.

Lecture seule : il rend les demandes d'installation rangées par le récepteur (/v1/install), telles
quelles, signature comprise. Le serveur les vérifie lui-même avec la clé publique de la plateforme
(infra/serveur/agent_installation.py) : le guichet ne décide de rien et n'a pas besoin d'être cru.

  uvicorn passerelle.guichet:app --host 10.42.2.10 --port 8444
  SAS_INSTALLATIONS  même fichier que le récepteur (défaut /var/lib/sas/installations.jsonl)
"""
import json
import os
from pathlib import Path

from fastapi import FastAPI

MAX = 50


def creer_app(installations: Path) -> FastAPI:
    installations = Path(installations)
    app = FastAPI(title="sas-pme guichet", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/v1/installations")
    def lister(apres: int = 0):
        if not installations.exists():
            return []
        sortie = []
        for ligne in installations.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                e = json.loads(ligne)
            except ValueError:
                continue
            if isinstance(e, dict) and isinstance(e.get("n"), int) and e["n"] > apres:
                sortie.append({k: e.get(k) for k in ("n", "demande", "signature")})
        return sortie[:MAX]

    return app


def __getattr__(nom: str):                # `uvicorn passerelle.guichet:app`
    if nom == "app":
        return creer_app(Path(os.environ.get("SAS_INSTALLATIONS",
                                             "/var/lib/sas/installations.jsonl")))
    raise AttributeError(nom)
