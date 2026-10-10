"""Interface web de la plateforme (A) : comptes et rôles, catalogue, demande de paquet, fiche.

Lancer : `uvicorn plateforme.web.app:app --port 8000`
Réglages : SAS_DB (chemin de la base), SAS_ADMIN_MOTDEPASSE, SAS_SECRET (signature des sessions),
SAS_TRAITEMENT_INTERVALLE (secondes entre deux appels de `traiter`, 60 ; 0 l'arrête),
SAS_ARCHIVES (dossier des archives téléchargées, `archives`).
Au premier lancement (base sans compte), le compte `admin` est créé avec SAS_ADMIN_MOTDEPASSE ;
sans elle, un mot de passe aléatoire est tiré et affiché. Ensuite, la variable est ignorée.
"""
import os
import re
import secrets
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from commun.modeles import Ecosysteme, Etat, Version
from plateforme.db.acces import Base, Compte, Role
from plateforme.web.fond import TacheDeFond

Demander = Callable[[Ecosysteme, str], None]
Traiter = Callable[[Base], object]
Horloge = Callable[[], datetime]
Delai = Callable[[], timedelta]

ADMIN_INITIAL = "admin"  # créé au premier lancement, si la base n'a aucun compte
MDP_MIN = 12
_IDENTIFIANT_VALIDE = re.compile(r"^[a-z][a-z0-9._-]{1,31}$")
# Noms PyPI (PEP 508) et npm (avec portée @org/nom), sans « .. » ni barre oblique libre.
_NOM_VALIDE = re.compile(r"^(@[a-z0-9][a-z0-9._-]*/)?[A-Za-z0-9][A-Za-z0-9._-]{0,213}$")

_gabarits = Jinja2Templates(directory=str(Path(__file__).with_name("gabarits")))


def _demander_par_defaut(base: Base) -> Demander:
    """Le vrai `pipeline.demander` (B), à qui on passe la base du web ; sans pipeline, un faux."""
    try:
        import plateforme.pipeline as pipeline

        def vrai(eco: Ecosysteme, nom: str) -> None:
            pipeline.demander(eco, nom, base=base)
        return vrai
    except ImportError:
        def faux(eco: Ecosysteme, nom: str) -> None:
            maintenant = datetime.now(timezone.utc)
            base.enregistrer_version(Version(ecosysteme=eco, nom=nom, version="latest",
                                             publiee_le=maintenant, detectee_le=maintenant,
                                             etat=Etat.EN_ATTENTE), acteur="faux-pipeline")
        return faux


def duree_lisible(d: timedelta) -> str:
    """« 1 j 02 h 41 min », « 5 h 03 min », « 1 min 30 s », « 9 s »."""
    s = max(0, int(d.total_seconds()))
    j, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if j:
        return f"{j} j {h:02d} h {m:02d} min"
    if h:
        return f"{h} h {m:02d} min"
    if m:
        return f"{m} min {s:02d} s"
    return f"{s} s"


def _delai_par_defaut() -> timedelta:
    """Le délai du pipeline (B), qui lit SAS_DELAI ; 3 jours sans le pipeline."""
    try:
        from plateforme.pipeline import pypi
    except ImportError:
        return timedelta(days=3)
    return pypi.delai()


def _texte_delai(d: timedelta) -> str:
    return f"{d.days} jours" if d == timedelta(days=d.days) else f"{int(d.total_seconds())} s"


def creer_app(base: Base, mot_de_passe: str, secret: str,
              demander: Demander | None = None,
              traiter: Traiter | None = None, intervalle: float = 60,
              horloge: Horloge | None = None, delai: Delai | None = None) -> FastAPI:
    """`mot_de_passe` ne sert qu'à créer le compte `admin` si la base n'a aucun compte.
    `traiter(base)` est appelée en tâche de fond tant que l'application tourne ; sans, rien."""

    @asynccontextmanager
    async def cycle(_app: FastAPI):
        if traiter is None:
            yield
            return
        tache = TacheDeFond(lambda: traiter(base), intervalle)
        tache.demarrer()
        try:
            yield
        finally:
            tache.arreter()

    app = FastAPI(title="sas-pme — plateforme agréée", lifespan=cycle)
    app.add_middleware(SessionMiddleware, secret_key=secret, same_site="strict",
                       https_only=False, max_age=8 * 3600)
    demander = demander or _demander_par_defaut(base)
    horloge = horloge or (lambda: datetime.now(timezone.utc))
    delai = delai or _delai_par_defaut
    if not base.lister_comptes():
        base.creer_compte(ADMIN_INITIAL, Role.ADMIN, mot_de_passe, acteur="systeme",
                          doit_changer=False)

    def exiger(request: Request, role: Role | None = None, *,
               avant_changement: bool = False) -> Compte:
        """Le compte connecté, relu en base à chaque requête : une désactivation ou un changement
        de rôle prend effet tout de suite. Un compte qui doit changer son mot de passe ne voit que
        la page prévue pour."""
        identifiant = request.session.get("utilisateur")
        compte = base.lire_compte(identifiant) if identifiant else None
        if compte is None or not compte.actif:
            request.session.clear()
            raise HTTPException(status_code=303, headers={"Location": "/connexion"})
        if compte.doit_changer and not avant_changement:
            raise HTTPException(status_code=303, headers={"Location": "/mot-de-passe"})
        if role is not None and compte.role is not role:
            raise HTTPException(status_code=403, detail=f"Réservé au rôle {role.value}.")
        return compte

    def page(request: Request, gabarit: str, compte: Compte | None, code: int = 200, **ctx):
        if compte is not None:
            ctx |= {"utilisateur": compte.identifiant, "role": compte.role.value}
        return _gabarits.TemplateResponse(request, gabarit, ctx, status_code=code)

    @app.get("/sante")
    def sante() -> dict:
        return {"ok": True}

    @app.get("/connexion", response_class=HTMLResponse)
    def page_connexion(request: Request):
        return page(request, "connexion.html", None, erreur=None)

    @app.post("/connexion")
    def connexion(request: Request, identifiant: str = Form(...), mot_de_passe: str = Form(...)):
        compte = base.authentifier(identifiant, mot_de_passe)
        if compte is None:
            base.journaliser(identifiant[:64], "connexion_refusee", "web", {})
            return page(request, "connexion.html", None, 401,
                        erreur="Identifiant ou mot de passe incorrect.")
        request.session.clear()
        request.session["utilisateur"] = compte.identifiant
        base.journaliser(compte.identifiant, "connexion", "web", {})
        return RedirectResponse("/mot-de-passe" if compte.doit_changer else "/", status_code=303)

    @app.post("/deconnexion")
    def deconnexion(request: Request):
        request.session.clear()
        return RedirectResponse("/connexion", status_code=303)

    @app.get("/", response_class=HTMLResponse)
    def catalogue(request: Request):
        return page(request, "catalogue.html", exiger(request), versions=base.lister_versions())

    @app.get("/demander", response_class=HTMLResponse)
    def page_demander(request: Request):
        return page(request, "demander.html", exiger(request), ecosystemes=list(Ecosysteme))

    @app.post("/demander")
    def demander_paquet(request: Request, ecosysteme: str = Form(...), nom: str = Form(...)):
        compte = exiger(request)
        nom = nom.strip()
        try:
            eco = Ecosysteme(ecosysteme)
        except ValueError:
            raise HTTPException(status_code=400, detail="Écosystème inconnu.")
        if not _NOM_VALIDE.match(nom) or ".." in nom:
            raise HTTPException(status_code=400, detail="Nom de paquet invalide.")
        base.journaliser(compte.identifiant, "demande_paquet", f"{eco.value}:{nom}", {})
        # Erreurs prévues de pipeline.demander (B) : on les dit sur le formulaire, pas en erreur 500.
        try:
            demander(eco, nom)
        except LookupError as e:
            return refuser(request, compte, nom, str(e), 404)
        except ValueError as e:
            return refuser(request, compte, nom, str(e), 400)
        except NotImplementedError:
            return refuser(request, compte, nom, f"{eco.value} n'est pas encore pris en charge.", 400)
        return RedirectResponse("/", status_code=303)

    def refuser(request: Request, compte: Compte, nom: str, message: str, code: int):
        return page(request, "demander.html", compte, code, ecosystemes=list(Ecosysteme),
                    erreur=message, nom=nom)

    @app.get("/versions/{ecosysteme}/{nom:path}/{version}", response_class=HTMLResponse)
    def fiche(request: Request, ecosysteme: str, nom: str, version: str):
        compte = exiger(request)
        try:
            eco = Ecosysteme(ecosysteme)
        except ValueError:
            raise HTTPException(status_code=404)
        f = base.fiche(eco, nom, version)
        if f is None:
            raise HTTPException(status_code=404)
        return page(request, "fiche.html", compte, fiche=f)

    # --- file d'attente ---------------------------------------------------------
    @app.get("/file-attente", response_class=HTMLResponse)
    def file_attente(request: Request):
        compte = exiger(request)
        maintenant = horloge()
        try:
            d, erreur = delai(), None
        except ValueError as e:  # SAS_DELAI illisible : on le dit, sans deviner un délai
            d, erreur = None, str(e)
        attente = []
        for v, _ in base.lister_avec_raison([Etat.NOUVELLE, Etat.EN_ATTENTE]):
            fin = v.publiee_le + d if d is not None else None
            reste = duree_lisible(fin - maintenant) if fin and fin > maintenant else None
            attente.append({"v": v, "fin": fin, "reste": reste})
        return page(request, "file_attente.html", compte, attente=attente, erreur=erreur,
                    delai=_texte_delai(d) if d is not None else None,
                    en_analyse=base.lister_avec_raison([Etat.EN_ANALYSE]),
                    a_revoir=base.lister_avec_raison([Etat.A_REVOIR]),
                    bloquees=base.lister_avec_raison([Etat.BLOQUEE]))

    # --- mot de passe -----------------------------------------------------------
    @app.get("/mot-de-passe", response_class=HTMLResponse)
    def page_mot_de_passe(request: Request):
        compte = exiger(request, avant_changement=True)
        return page(request, "mot_de_passe.html", compte, oblige=compte.doit_changer)

    @app.post("/mot-de-passe")
    def changer_mot_de_passe(request: Request, actuel: str = Form(...), nouveau: str = Form(...),
                             confirmation: str = Form(...)):
        compte = exiger(request, avant_changement=True)
        erreur = None
        if base.authentifier(compte.identifiant, actuel) is None:
            erreur = "Le mot de passe actuel est incorrect."
        elif len(nouveau) < MDP_MIN:
            erreur = f"Le nouveau mot de passe doit faire au moins {MDP_MIN} caractères."
        elif nouveau != confirmation:
            erreur = "Les deux mots de passe ne correspondent pas."
        elif nouveau == actuel:
            erreur = "Le nouveau mot de passe doit être différent de l'actuel."
        if erreur:
            return page(request, "mot_de_passe.html", compte, 400, oblige=compte.doit_changer,
                        erreur=erreur)
        base.changer_mot_de_passe(compte.identifiant, nouveau, acteur=compte.identifiant)
        return RedirectResponse("/", status_code=303)

    # --- comptes (admin) --------------------------------------------------------
    def page_comptes(request: Request, admin: Compte, code: int = 200, **ctx):
        return page(request, "comptes.html", admin, code, comptes=base.lister_comptes(),
                    roles=list(Role), **ctx)

    @app.get("/comptes", response_class=HTMLResponse)
    def comptes(request: Request):
        return page_comptes(request, exiger(request, Role.ADMIN))

    @app.post("/comptes")
    def creer_compte(request: Request, identifiant: str = Form(...), role: str = Form(...)):
        admin = exiger(request, Role.ADMIN)
        identifiant = identifiant.strip()
        if not _IDENTIFIANT_VALIDE.match(identifiant):
            return page_comptes(request, admin, 400, erreur="Identifiant invalide : 2 à 32 "
                                "caractères, minuscules, chiffres, « . », « _ » ou « - ».")
        try:
            mdp = secrets.token_urlsafe(12)
            base.creer_compte(identifiant, Role(role), mdp, acteur=admin.identifiant)
        except ValueError as e:
            return page_comptes(request, admin, 400, erreur=f"Création refusée : {e}.")
        # Le mot de passe initial n'est affiché qu'ici, une fois ; il devra être changé.
        return page_comptes(request, admin, cree=identifiant, mot_de_passe=mdp)

    def modifier(request: Request, action: Callable[[Compte], None]):
        admin = exiger(request, Role.ADMIN)
        try:
            action(admin)
        except KeyError:
            raise HTTPException(status_code=404)
        except ValueError as e:
            return page_comptes(request, admin, 400, erreur=f"Refusé : {e}.")
        return RedirectResponse("/comptes", status_code=303)

    @app.post("/comptes/{identifiant}/role")
    def changer_role(request: Request, identifiant: str, role: str = Form(...)):
        return modifier(request, lambda admin: base.changer_role(
            identifiant, Role(role), acteur=admin.identifiant))

    @app.post("/comptes/{identifiant}/desactiver")
    def desactiver(request: Request, identifiant: str):
        return modifier(request, lambda admin: base.desactiver(
            identifiant, acteur=admin.identifiant))

    return app


def _depuis_environnement() -> FastAPI:
    mdp = os.environ.get("SAS_ADMIN_MOTDEPASSE")
    if not mdp:
        mdp = secrets.token_urlsafe(12)
        print(f"[sas-pme] Si la base est neuve, mot de passe du compte admin : {mdp}",
              file=sys.stderr)
    secret = os.environ.get("SAS_SECRET") or secrets.token_urlsafe(32)
    intervalle = float(os.environ.get("SAS_TRAITEMENT_INTERVALLE", "60"))
    return creer_app(base=Base(os.environ.get("SAS_DB", "sas.db")), mot_de_passe=mdp, secret=secret,
                     traiter=_traiter_par_defaut() if intervalle > 0 else None,
                     intervalle=intervalle)


def _traiter_par_defaut() -> Traiter:
    """Le vrai `pipeline.traitement.traiter` (B), avec le dossier d'archives de SAS_ARCHIVES."""
    from plateforme.pipeline.traitement import traiter

    dossier = Path(os.environ.get("SAS_ARCHIVES", "archives"))
    return lambda base: traiter(base, dossier=dossier)


def __getattr__(nom: str):
    # `uvicorn plateforme.web.app:app` : l'application n'est créée qu'à la demande,
    # pour que l'import du module (tests) n'ouvre aucune base.
    if nom == "app":
        globals()["app"] = _depuis_environnement()
        return globals()["app"]
    raise AttributeError(nom)
