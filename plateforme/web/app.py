"""Interface web de la plateforme (A) — M0 : connexion fixe, catalogue, demande de paquet, fiche.

Lancer : `uvicorn plateforme.web.app:app --port 8000`
Réglages : SAS_DB (chemin de la base), SAS_ADMIN_MOTDEPASSE, SAS_SECRET (signature des sessions).
Sans SAS_ADMIN_MOTDEPASSE, un mot de passe aléatoire est tiré et affiché au démarrage.
"""
import hmac
import os
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from commun.modeles import Ecosysteme, Etat, Version
from plateforme.db.acces import Base

Demander = Callable[[Ecosysteme, str], None]

IDENTIFIANT = "admin"  # M0 : un seul compte ; comptes et rôles en M1
# Noms PyPI (PEP 508) et npm (avec portée @org/nom), sans « .. » ni barre oblique libre.
_NOM_VALIDE = re.compile(r"^(@[a-z0-9][a-z0-9._-]*/)?[A-Za-z0-9][A-Za-z0-9._-]{0,213}$")

_gabarits = Jinja2Templates(directory=str(Path(__file__).with_name("gabarits")))


def _demander_par_defaut(base: Base) -> Demander:
    """Le vrai `pipeline.demander` (B) s'il existe ; sinon un faux qui enregistre la version « latest »."""
    try:
        from plateforme.pipeline import demander  # type: ignore[attr-defined]
        return demander
    except ImportError:
        def faux(eco: Ecosysteme, nom: str) -> None:
            maintenant = datetime.now(timezone.utc)
            base.enregistrer_version(Version(ecosysteme=eco, nom=nom, version="latest",
                                             publiee_le=maintenant, detectee_le=maintenant,
                                             etat=Etat.EN_ATTENTE), acteur="faux-pipeline")
        return faux


def creer_app(base: Base, mot_de_passe: str, secret: str,
              demander: Demander | None = None) -> FastAPI:
    app = FastAPI(title="sas-pme — plateforme agréée")
    app.add_middleware(SessionMiddleware, secret_key=secret, same_site="strict",
                       https_only=False, max_age=8 * 3600)
    demander = demander or _demander_par_defaut(base)
    attendu = mot_de_passe

    def utilisateur(request: Request) -> str | None:
        return request.session.get("utilisateur")

    def exiger(request: Request) -> str:
        u = utilisateur(request)
        if u is None:
            raise HTTPException(status_code=303, headers={"Location": "/connexion"})
        return u

    @app.get("/sante")
    def sante() -> dict:
        return {"ok": True}

    @app.get("/connexion", response_class=HTMLResponse)
    def page_connexion(request: Request):
        return _gabarits.TemplateResponse(request, "connexion.html", {"erreur": None})

    @app.post("/connexion")
    def connexion(request: Request, identifiant: str = Form(...), mot_de_passe: str = Form(...)):
        bon = hmac.compare_digest(identifiant.encode(), IDENTIFIANT.encode()) & \
            hmac.compare_digest(mot_de_passe.encode(), attendu.encode())
        if not bon:
            base.journaliser(identifiant[:64], "connexion_refusee", "web", {})
            return _gabarits.TemplateResponse(request, "connexion.html",
                                              {"erreur": "Identifiant ou mot de passe incorrect."},
                                              status_code=401)
        request.session.clear()
        request.session["utilisateur"] = identifiant
        base.journaliser(identifiant, "connexion", "web", {})
        return RedirectResponse("/", status_code=303)

    @app.post("/deconnexion")
    def deconnexion(request: Request):
        request.session.clear()
        return RedirectResponse("/connexion", status_code=303)

    @app.get("/", response_class=HTMLResponse)
    def catalogue(request: Request):
        u = exiger(request)
        versions = base.lister_versions()
        return _gabarits.TemplateResponse(request, "catalogue.html",
                                          {"utilisateur": u, "versions": versions})

    @app.get("/demander", response_class=HTMLResponse)
    def page_demander(request: Request):
        u = exiger(request)
        return _gabarits.TemplateResponse(request, "demander.html",
                                          {"utilisateur": u, "ecosystemes": list(Ecosysteme)})

    @app.post("/demander")
    def demander_paquet(request: Request, ecosysteme: str = Form(...), nom: str = Form(...)):
        u = exiger(request)
        nom = nom.strip()
        try:
            eco = Ecosysteme(ecosysteme)
        except ValueError:
            raise HTTPException(status_code=400, detail="Écosystème inconnu.")
        if not _NOM_VALIDE.match(nom) or ".." in nom:
            raise HTTPException(status_code=400, detail="Nom de paquet invalide.")
        base.journaliser(u, "demande_paquet", f"{eco.value}:{nom}", {})
        demander(eco, nom)
        return RedirectResponse("/", status_code=303)

    @app.get("/versions/{ecosysteme}/{nom:path}/{version}", response_class=HTMLResponse)
    def fiche(request: Request, ecosysteme: str, nom: str, version: str):
        u = exiger(request)
        try:
            eco = Ecosysteme(ecosysteme)
        except ValueError:
            raise HTTPException(status_code=404)
        f = base.fiche(eco, nom, version)
        if f is None:
            raise HTTPException(status_code=404)
        return _gabarits.TemplateResponse(request, "fiche.html", {"utilisateur": u, "fiche": f})

    return app


def _depuis_environnement() -> FastAPI:
    mdp = os.environ.get("SAS_ADMIN_MOTDEPASSE")
    if not mdp:
        mdp = secrets.token_urlsafe(12)
        print(f"[sas-pme] Mot de passe admin tiré au hasard : {mdp}", file=sys.stderr)
    secret = os.environ.get("SAS_SECRET") or secrets.token_urlsafe(32)
    return creer_app(base=Base(os.environ.get("SAS_DB", "sas.db")), mot_de_passe=mdp, secret=secret)


def __getattr__(nom: str):
    # `uvicorn plateforme.web.app:app` : l'application n'est créée qu'à la demande,
    # pour que l'import du module (tests) n'ouvre aucune base.
    if nom == "app":
        globals()["app"] = _depuis_environnement()
        return globals()["app"]
    raise AttributeError(nom)
