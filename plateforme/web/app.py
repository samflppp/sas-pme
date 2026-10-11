"""Interface web de la plateforme (A) : comptes et rôles, catalogue, demande de paquet, fiche.

Lancer : `uvicorn plateforme.web.app:app --port 8000`
Réglages : SAS_DB (chemin de la base), SAS_CLE_JOURNAL (clé HMAC du journal, obligatoire),
SAS_ADMIN_MOTDEPASSE, SAS_SECRET (signature des sessions),
SAS_TRAITEMENT_INTERVALLE (secondes entre deux appels de `traiter`, 60 ; 0 l'arrête),
SAS_ARCHIVES (dossier des archives téléchargées, `archives`).
La page « Inventaire » lit la passerelle (`signature.lire_inventaire`, C) à chaque affichage.
La page « Direct » suit les versions d'une demande : étapes de la pipeline en direct (Server-Sent
Events, `direct.Diffusion` alimentée par `traiter(..., suivi=...)`) et relues au journal.
Au premier lancement (base sans compte), le compte `admin` est créé avec SAS_ADMIN_MOTDEPASSE
(MDP_MIN caractères au moins, sinon refus de démarrer) ; sans elle, un mot de passe aléatoire est
tiré et affiché. Ensuite, la variable est ignorée.
"""
import asyncio
import json
import os
import re
import time
import secrets
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from packaging.utils import canonicalize_name, canonicalize_version
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware

from commun.modeles import Ecosysteme, EntreeInventaire, Etat, Version
from plateforme.db.acces import Base, Compte, Role
from plateforme.web import catalogue as cat
from plateforme.web import direct as dr
from plateforme.web.fond import TacheDeFond

# demander(eco, nom) : pipeline.demander (B) ; rend la version demandée (None : inconnue)
Demander = Callable[[Ecosysteme, str], Version | None]
# decider(base, eco, nom, version, etat, raison, acteur) : pipeline.decision_humaine (B)
Decider = Callable[[Base, Ecosysteme, str, str, Etat, str, str], object]
# revoquer(eco, nom, version, raison) : signature.revoquer (C), qui retire l'archive de la passerelle
Revoquer = Callable[[Ecosysteme, str, str, str], None]
Traiter = Callable[[Base], object]
# lire_inventaire() : signature.lire_inventaire (C), ce que les serveurs ont installé
LireInventaire = Callable[[], list[EntreeInventaire]]
# installer(eco, nom, demande) : signature.demander_installation ; lire_acces(apres) : signature.lire_acces
Installer = Callable[[Ecosysteme, str, int], int]
LireAcces = Callable[[int], dict]
Horloge = Callable[[], datetime]
Delai = Callable[[], timedelta]

ADMIN_INITIAL = "admin"  # créé au premier lancement, si la base n'a aucun compte
MDP_MIN = 12
PAGE_JOURNAL = 100
_IDENTIFIANT_VALIDE = re.compile(r"^[a-z][a-z0-9._-]{1,31}$")
# Noms PyPI (PEP 508) et npm (avec portée @org/nom), sans « .. » ni barre oblique libre.
_NOM_VALIDE = re.compile(r"^(@[a-z0-9][a-z0-9._-]*/)?[A-Za-z0-9][A-Za-z0-9._-]{0,213}$")

_gabarits = Jinja2Templates(directory=str(Path(__file__).with_name("gabarits")))
LIBELLES = {Etat.NOUVELLE: "nouvelle", Etat.EN_ATTENTE: "en attente", Etat.EN_ANALYSE: "en analyse",
            Etat.A_REVOIR: "à revoir", Etat.APPROUVEE: "approuvée", Etat.BLOQUEE: "bloquée",
            Etat.PUBLIEE: "publiée", Etat.REVOQUEE: "révoquée"}


def libelle(etat: object) -> str:
    """« en attente » pour `en_attente` ; une valeur inconnue (journal ancien) reste telle quelle."""
    try:
        return LIBELLES[Etat(etat)]
    except ValueError:
        return str(etat)


_gabarits.env.filters["libelle"] = libelle


def _demander_par_defaut(base: Base) -> Demander:
    """Le vrai `pipeline.demander` (B), à qui on passe la base du web ; sans pipeline, un faux."""
    try:
        import plateforme.pipeline as pipeline

        def vrai(eco: Ecosysteme, nom: str) -> Version:
            return pipeline.demander(eco, nom, base=base)
        return vrai
    except ImportError:
        def faux(eco: Ecosysteme, nom: str) -> None:
            maintenant = datetime.now(timezone.utc)
            base.enregistrer_version(Version(ecosysteme=eco, nom=nom, version="latest",
                                             publiee_le=maintenant, detectee_le=maintenant,
                                             etat=Etat.EN_ATTENTE), acteur="faux-pipeline")
        return faux


def _decider_par_defaut(*args) -> object:
    """Le vrai `pipeline.decision_humaine` (B), importé seulement au premier clic."""
    from plateforme.pipeline import decision_humaine
    return decision_humaine(*args)


def _lire_inventaire_par_defaut() -> list[EntreeInventaire]:
    """Le vrai `signature.lire_inventaire` (C), importé seulement à l'affichage de la page."""
    from plateforme.signature import lire_inventaire
    return lire_inventaire()


def _passerelle_configuree() -> bool:
    return bool(os.environ.get("SAS_PASSERELLE_URL"))


def _installer_par_defaut(*args) -> int:
    from plateforme.signature import demander_installation
    return demander_installation(*args)


def _lire_acces_par_defaut(apres: int) -> dict:
    from plateforme.signature import lire_acces
    return lire_acces(apres)


def _revoquer_par_defaut(*args) -> None:
    """Le vrai `signature.revoquer` (C), importé seulement au premier clic."""
    from plateforme.signature import revoquer
    revoquer(*args)


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


def _compter(valeurs: list[str]) -> list[str]:
    """« exfil.demo.invalid (×6) » : une ligne par valeur, dans l'ordre d'apparition."""
    vues: dict[str, int] = {}
    for v in valeurs:
        vues[v] = vues.get(v, 0) + 1
    return [f"{v} (×{n})" if n > 1 else v for v, n in vues.items()]


def _lien_sur(url: object) -> str | None:
    """Seuls http et https deviennent des liens : une preuve vient parfois d'Internet."""
    return url if isinstance(url, str) and re.match(r"^https?://", url, re.I) else None


_SUJET_VERSION = re.compile(r"^(pypi|npm):(.+)@([^@]+)$")


def _lien_fiche(sujet: str) -> str | None:
    """« pypi:requests@2.32.4 » mène à la fiche de la version ; les autres sujets, nulle part."""
    m = _SUJET_VERSION.match(sujet)
    return f"/versions/{m[1]}/{m[2]}/{m[3]}" if m else None


# traiter() (B) écrit « publication échouée : <message> » et laisse la version approuvée ;
# un refus de la passerelle a pour message « passerelle <code> : <motif> » (PublicationRefusee, C).
_ECHEC_PUBLICATION = re.compile(r"^publication échouée : (?:passerelle (\d{3}) : )?(.*)$", re.S)


def etat_publication(etat: Etat, raison: str | None) -> dict | None:
    """Pour une version approuvée mais pas publiée : un refus de la passerelle (signature,
    hash, nonce…) n'est pas une panne réseau. None si la version n'est pas dans ce cas."""
    m = _ECHEC_PUBLICATION.match(raison or "") if etat is Etat.APPROUVEE else None
    if m is None:
        return None
    if m[1]:
        return {"sorte": "refus", "code": m[1], "motif": m[2]}
    return {"sorte": "panne", "motif": m[2]}


def compter_par_etat(versions: list[Version]) -> dict[Etat, int]:
    """Le nombre de versions dans chaque état, tous les états présents (même à 0), dans l'ordre du
    cycle de vie."""
    compte = dict.fromkeys(Etat, 0)
    for v in versions:
        compte[v.etat] += 1
    return compte


DERNIERS_BLOCAGES = 5
DERNIERES = 8            # versions récentes sur la racine du catalogue


@dataclass(frozen=True)
class LigneInventaire:
    entree: EntreeInventaire     # ce que dit la passerelle
    version: Version | None      # la même version sur la plateforme ; None si inconnue
    alerte: str | None           # None : publiée, rien à signaler


def _cle_inventaire(eco: Ecosysteme, nom: str, version: str) -> tuple[Ecosysteme, str, str]:
    """Le dépôt et la plateforme n'écrivent pas toujours pareil (« Demo_X 1.10.0 » et « demo-x
    1.10 ») : noms PEP 503 et versions PEP 440 normalisés des deux côtés (relecture de B)."""
    try:
        version = canonicalize_version(version)
    except ValueError:
        pass                     # une version illisible se compare telle quelle
    return eco, canonicalize_name(nom), version


def _alerte(e: EntreeInventaire, v: Version | None) -> str | None:
    if v is None:
        return "Inconnue de la plateforme : présente sur le dépôt sans y avoir été approuvée."
    if v.etat is Etat.PUBLIEE:
        return None
    if v.etat in (Etat.REVOQUEE, Etat.BLOQUEE):
        quoi = "Révoquée" if v.etat is Etat.REVOQUEE else "Bloquée"
        if e.telechargements:
            return (f"{quoi} depuis, et téléchargée {e.telechargements} fois : "
                    "un serveur l'a peut-être encore.")
        return f"{quoi} depuis, mais encore sur le dépôt."
    return f"Sur le dépôt alors qu'elle est « {v.etat.value} » sur la plateforme."


def croiser(entrees: list[EntreeInventaire], versions: list[Version]) -> list[LigneInventaire]:
    """Chaque entrée de l'inventaire avec l'état de sa version ; les alertes d'abord (contrat § 4 :
    « installée sur les serveurs, mais révoquée ou bloquée depuis » est celle qui compte)."""
    par_cle = {_cle_inventaire(v.ecosysteme, v.nom, v.version): v for v in versions}
    lignes = []
    for e in entrees:
        v = par_cle.get(_cle_inventaire(e.ecosysteme, e.nom, e.version))
        lignes.append(LigneInventaire(e, v, _alerte(e, v)))
    return sorted(lignes, key=lambda l: l.alerte is None)   # tri stable : l'ordre reste sinon


def _delai_par_defaut() -> timedelta:
    """Le délai du pipeline (B), qui lit SAS_DELAI ; 3 jours sans le pipeline."""
    try:
        from plateforme.pipeline import pypi
    except ImportError:
        return timedelta(days=3)
    return pypi.delai()


def meme_origine(request: Request) -> bool:
    """Le POST vient-il d'une page de ce site ? `Origin`, sinon `Referer`, comparé à `Host`.
    Sans aucun des deux, ce n'est pas un navigateur (curl, script) : pas de CSRF possible."""
    source = request.headers.get("origin") or request.headers.get("referer")
    if source is None:
        return True
    hote = request.headers.get("host", "").lower()
    p = urlsplit(source)
    return bool(hote) and p.scheme.lower() in ("http", "https") and p.netloc.lower() == hote


def _texte_delai(d: timedelta) -> str:
    return f"{d.days} jours" if d == timedelta(days=d.days) else f"{int(d.total_seconds())} s"


def creer_app(base: Base, mot_de_passe: str, secret: str,
              demander: Demander | None = None,
              traiter: Traiter | None = None, intervalle: float = 60,
              horloge: Horloge | None = None, delai: Delai | None = None,
              decider: Decider | None = None, revoquer: Revoquer | None = None,
              lire_inventaire: LireInventaire | None = None,
              archives: Path | None = None, images: Path | None = None,
              diffusion: dr.Diffusion | None = None, duree_flux: float = 600,
              installer: Installer | None = None, lire_acces: LireAcces | None = None,
              index_serveur: str | None = None) -> FastAPI:
    """`installer` et `lire_acces` (panneau « Serveur » de la page Direct) : par défaut, ceux de la
    signature (C) si la passerelle est configurée (SAS_PASSERELLE_URL), sinon aucun."""
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
    # Styles, polices et scripts de l'interface : servis ici, sans aucune ressource extérieure.
    app.mount("/statique", StaticFiles(directory=Path(__file__).with_name("statique")), name="statique")
    app.add_middleware(SessionMiddleware, secret_key=secret, same_site="strict",
                       https_only=False, max_age=8 * 3600)

    @app.middleware("http")
    async def verifier_origine(request: Request, suite):
        """Relecture de B, A5 : un POST venu d'une autre page (CSRF) est refusé. `same_site` ne
        suffit pas : deux ports de localhost (le tunnel de la démo) sont le même « site »."""
        if request.method not in ("GET", "HEAD", "OPTIONS") and not meme_origine(request):
            source = request.headers.get("origin") or request.headers.get("referer") or ""
            await run_in_threadpool(base.journaliser, "web", "origine_refusee", request.url.path,
                                    {"origine": source[:200]})
            return HTMLResponse("Requête refusée : elle ne vient pas d'une page de cette origine.",
                                status_code=403)
        return await suite(request)
    demander = demander or _demander_par_defaut(base)
    horloge = horloge or (lambda: datetime.now(timezone.utc))
    delai = delai or _delai_par_defaut
    decider = decider or _decider_par_defaut
    revoquer = revoquer or _revoquer_par_defaut
    lire_inventaire = lire_inventaire or _lire_inventaire_par_defaut
    archives = archives if archives is not None else Path(os.environ.get("SAS_ARCHIVES", "archives"))
    images = images if images is not None else Path(__file__).with_name("images-agreees.json")
    diffusion = diffusion or dr.Diffusion()
    app.state.diffusion = diffusion
    if installer is None and lire_acces is None and _passerelle_configuree():
        installer, lire_acces = _installer_par_defaut, _lire_acces_par_defaut
    index_serveur = index_serveur or os.environ.get("SAS_INDEX_SERVEUR",
                                                    "http://10.42.2.10:8080/simple/")
    lectures: dict[int, tuple[float, dict]] = {}

    def lire_acces_court(apres: int) -> dict:
        """Une lecture par seconde au plus pour un même point de départ : le flux en fait souvent."""
        t, r = lectures.get(apres, (0.0, None))
        if r is None or time.monotonic() - t > 1.0:
            r = lire_acces(apres)
            lectures.clear()
            lectures[apres] = (time.monotonic(), r)
        return r
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
        # Un changement de mot de passe change la génération : les autres sessions sont coupées (A5).
        if (compte is None or not compte.actif
                or request.session.get("generation") != compte.generation):
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
        request.session["generation"] = compte.generation
        base.journaliser(compte.identifiant, "connexion", "web", {})
        return RedirectResponse("/mot-de-passe" if compte.doit_changer else "/", status_code=303)

    @app.post("/deconnexion")
    def deconnexion(request: Request):
        request.session.clear()
        return RedirectResponse("/connexion", status_code=303)

    # --- catalogue en arborescence -----------------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    def catalogue(request: Request):
        compte = exiger(request)
        versions = base.lister_versions()
        dossiers = [{"nom": e.value, "n": len(cat.paquets(versions, e)), "sorte": "paquet"}
                    for e in Ecosysteme]
        dossiers.append({"nom": "images", "n": len(cat.images(images)), "sorte": "image"})
        return page(request, "catalogue.html", compte, niveau="racine", arbo=[],
                    dossiers=dossiers, compteurs=compter_par_etat(versions),
                    recentes=sorted(versions, key=lambda v: v.detectee_le, reverse=True)[:DERNIERES])

    def ecosysteme_ou_404(valeur: str) -> Ecosysteme:
        try:
            return Ecosysteme(valeur)
        except ValueError:
            raise HTTPException(status_code=404)

    @app.get("/catalogue/{ecosysteme}", response_class=HTMLResponse)
    def catalogue_ecosysteme(request: Request, ecosysteme: str):
        compte = exiger(request)
        if ecosysteme == "images":
            return page(request, "catalogue.html", compte, niveau="images", arbo=["images"],
                        images=cat.images(images))
        eco = ecosysteme_ou_404(ecosysteme)
        return page(request, "catalogue.html", compte, niveau="ecosysteme", arbo=[eco.value],
                    eco=eco, paquets=cat.paquets(base.lister_versions(), eco))

    @app.get("/catalogue/{ecosysteme}/{reste:path}", response_class=HTMLResponse)
    def catalogue_paquet(request: Request, ecosysteme: str, reste: str):
        """`<nom>` (un nom npm peut contenir « / »), `<nom>/-/<version>`, `<nom>/-/<version>/<fichier>`.
        Tout est relu dans la base : un nom, une version ou un fichier inconnus donnent 404."""
        compte = exiger(request)
        eco = ecosysteme_ou_404(ecosysteme)
        nom, _, apres = reste.partition("/-/")
        p = cat.paquet(base.lister_versions(), eco, nom)
        if p is None:
            raise HTTPException(status_code=404)
        if not apres:
            attente = None
            if p.suivante is not None and p.suivante.etat in (Etat.NOUVELLE, Etat.EN_ATTENTE):
                try:
                    fin = p.suivante.publiee_le + delai()
                    attente = duree_lisible(fin - horloge()) if fin > horloge() else "au prochain tour"
                except ValueError:
                    attente = None
            return page(request, "catalogue.html", compte, niveau="paquet", arbo=[eco.value, nom],
                        eco=eco, p=p, attente=attente)
        version, _, nom_fichier = apres.partition("/")
        f = base.fiche(eco, nom, version)
        if f is None:
            raise HTTPException(status_code=404)
        fichiers = cat.fichiers_version(f, archives)
        if not nom_fichier:
            return page(request, "catalogue.html", compte, niveau="version",
                        arbo=[eco.value, nom, version], eco=eco, p=p, fiche=f, fichiers=fichiers,
                        taille=cat.taille_lisible)
        blob = next((x for x in fichiers if x.nom == nom_fichier and x.contenu is not None), None)
        if blob is None:
            raise HTTPException(status_code=404)
        return page(request, "catalogue.html", compte, niveau="blob",
                    arbo=[eco.value, nom, version, nom_fichier], eco=eco, p=p, fiche=f, blob=blob,
                    lignes=blob.contenu.splitlines(), taille=cat.taille_lisible)

    @app.get("/tableau-de-bord", response_class=HTMLResponse)
    def tableau_de_bord(request: Request):
        compte = exiger(request)
        versions = base.lister_versions()
        bloquees = base.lister_avec_raison([Etat.BLOQUEE, Etat.REVOQUEE])
        # lister_avec_raison trie par date de publication : les plus récentes d'abord
        derniers = bloquees[::-1][:DERNIERS_BLOCAGES]
        journal = None
        if compte.role is Role.ADMIN:  # le journal est réservé aux admins (comptes, identifiants)
            intact, casse = base.verifier_journal()
            journal = {"entrees": base.compter_journal(), "intact": intact, "casse": casse}
        return page(request, "tableau.html", compte, compteurs=compter_par_etat(versions),
                    total=len(versions), a_trancher=base.lister_avec_raison([Etat.A_REVOIR]),
                    derniers=derniers, journal=journal)

    @app.get("/inventaire", response_class=HTMLResponse)
    def inventaire(request: Request):
        compte = exiger(request)
        try:
            entrees = lire_inventaire()
        except Exception as e:  # passerelle injoignable ou refus : on le dit, l'instantané reste
            return page(request, "inventaire.html", compte, 502, lignes=[], alertes=0,
                        erreur=f"{type(e).__name__} : {e}")
        base.enregistrer_inventaire(entrees)
        lignes = croiser(entrees, base.lister_versions())
        return page(request, "inventaire.html", compte, lignes=lignes,
                    alertes=sum(l.alerte is not None for l in lignes), erreur=None)

    def demandes_recentes(n: int = 20) -> list[dict]:
        sortie = []
        for e in base.journal_recent(n, q="demande_resolue"):
            d = dr.demande(e)
            if d is None:
                continue
            principale = None
            if d.sujets and (cle := dr._decouper(d.sujets[0])):
                principale = base.lire_version(*cle)
            sortie.append({"d": d, "principale": principale})
        return sortie

    @app.get("/demander", response_class=HTMLResponse)
    def page_demander(request: Request):
        return page(request, "demander.html", exiger(request), ecosystemes=list(Ecosysteme),
                    demandes=demandes_recentes())

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
        avant = dernier_seq()
        try:
            principale = demander(eco, nom)
        except LookupError as e:
            return refuser(request, compte, nom, str(e), 404)
        except ValueError as e:
            return refuser(request, compte, nom, str(e), 400)
        except NotImplementedError:
            return refuser(request, compte, nom, f"{eco.value} n'est pas encore pris en charge.", 400)
        # Les versions que la demande a fait entrer (le paquet et ses dépendances) ; une version déjà
        # connue n'est pas re-détectée : la version demandée est alors celle que rend demander().
        detectees = [e.sujet for e in reversed(base.journal_recent(500)) if e.seq > avant
                     and e.action == "version_detectee" and e.sujet.startswith(f"{eco.value}:")]
        tete = [f"{eco.value}:{principale.nom}@{principale.version}"] if principale else []
        sujets = list(dict.fromkeys([*tete, *detectees]))
        base.journaliser(compte.identifiant, "demande_resolue", f"{eco.value}:{nom}",
                         {"versions": sujets})
        n = dernier_seq()
        if installer is not None:
            demander_au_serveur(compte, eco, nom, n)
        return RedirectResponse(f"/direct?demande={n}", status_code=303)

    def demander_au_serveur(compte: Compte, eco: Ecosysteme, nom: str, n: int) -> None:
        """Le serveur de démo installe ce qu'on vient de demander : il recevra la dernière version
        vérifiée. On note où en est le journal d'accès, pour ne montrer que la suite. Un refus ou
        une panne se dit au journal et sur la page ; la demande, elle, est faite."""
        try:
            depuis = lire_acces(10 ** 9)["total"]
            rang = installer(eco, nom, n)
        except Exception as e:  # noqa: BLE001 — refus, réseau : dit, jamais une erreur 500
            base.journaliser(compte.identifiant, "installation_echouee", f"{eco.value}:{nom}",
                             {"demande": n, "erreur": str(e)[:300]})
            return
        base.journaliser(compte.identifiant, "installation_demandee", f"{eco.value}:{nom}",
                         {"demande": n, "rang": rang, "acces_depuis": depuis})

    def dernier_seq() -> int:
        dernieres = base.journal_recent(1)
        return dernieres[0].seq if dernieres else 0

    def refuser(request: Request, compte: Compte, nom: str, message: str, code: int):
        return page(request, "demander.html", compte, code, ecosystemes=list(Ecosysteme),
                    erreur=message, nom=nom, demandes=demandes_recentes())

    # --- direct : les versions d'une demande, étape par étape -----------------------------------
    def demande_ou_404(n: int | None) -> dr.Demande | None:
        """La demande n° n (seq de sa résolution au journal) ; sans n, la plus récente (None : aucune)."""
        if n is None:
            recentes = [d for e in base.journal_recent(20, q="demande_resolue")
                        if (d := dr.demande(e))]
            return recentes[0] if recentes else None
        trouvees = base.journal_recent(1, avant=n + 1)
        d = dr.demande(trouvees[0]) if trouvees and trouvees[0].seq == n else None
        if d is None:
            raise HTTPException(status_code=404)
        return d

    def delai_ou_none() -> timedelta | None:
        try:
            return delai()
        except ValueError:
            return None

    def instantane(d: dr.Demande) -> dict:
        maintenant, delai_ = horloge(), delai_ou_none()
        i = dr.instantane(base, diffusion, d, maintenant, delai_, libelle, duree_lisible)
        installations = [e for e in base.journal_recent(200, q="installation_")
                         if e.action in ("installation_demandee", "installation_echouee")]
        celle = next((e for e in installations if e.charge.get("demande") == d.seq), None)
        apres = [e for e in installations if celle and e.seq > celle.seq
                 and e.action == "installation_demandee"]
        i["serveur"] = dr.serveur(base, d, celle, apres[-1] if apres else None,
                                  lire_acces_court if lire_acces else None, maintenant, delai_,
                                  libelle, duree_lisible, index_serveur)
        return i

    @app.get("/direct", response_class=HTMLResponse)
    def page_direct(request: Request, demande: int | None = None):
        compte = exiger(request)
        d = demande_ou_404(demande)
        return page(request, "direct.html", compte, i=instantane(d) if d else None,
                    demandes=demandes_recentes(10))

    @app.get("/direct/instantane")
    def direct_instantane(request: Request, demande: int):
        exiger(request)
        return JSONResponse(instantane(demande_ou_404(demande)))

    @app.get("/direct/flux")
    async def direct_flux(request: Request, demande: int):
        """Server-Sent Events : l'instantané à chaque nouvelle de la pipeline, et au moins toutes les
        secondes (un état changé ailleurs) ; seulement s'il a changé. La connexion dure au plus
        `duree_flux` secondes ; EventSource la rouvre seul."""
        await run_in_threadpool(exiger, request)
        d = await run_in_threadpool(demande_ou_404, demande)

        async def evenements():
            yield "retry: 1000\n\n"
            fin, dernier, vu, prochain = time.monotonic() + duree_flux, None, -1, 0.0
            while True:
                if diffusion.seq != vu or time.monotonic() >= prochain:
                    vu, prochain = diffusion.seq, time.monotonic() + 1.0
                    texte = json.dumps(await run_in_threadpool(instantane, d), ensure_ascii=False)
                    if texte != dernier:
                        dernier = texte
                        yield f"data: {texte}\n\n"
                if time.monotonic() >= fin or await request.is_disconnected():
                    return
                await asyncio.sleep(0.25)

        return StreamingResponse(evenements(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/versions/{ecosysteme}/{nom:path}/{version}", response_class=HTMLResponse)
    def fiche(request: Request, ecosysteme: str, nom: str, version: str):
        return afficher_fiche(request, exiger(request), ecosysteme, nom, version)

    def afficher_fiche(request: Request, compte: Compte, ecosysteme: str, nom: str, version: str,
                       code: int = 200, erreur: str | None = None):
        try:
            eco = Ecosysteme(ecosysteme)
        except ValueError:
            raise HTTPException(status_code=404)
        f = base.fiche(eco, nom, version)
        if f is None:
            raise HTTPException(status_code=404)
        signaux = sorted(f.signaux, key=lambda s: -s.niveau.rang)  # le plus grave d'abord
        r = f.rapport_sandbox
        sandbox = None if r is None else {
            "dns": _compter(r.requetes_dns), "connexions": _compter(r.connexions),
            "fichiers": _compter(r.fichiers_sensibles), "leurres": _compter(r.leurres_lus),
            "processus": _compter(r.processus), "rapport": r}
        autres = [v for v in base.versions_du_paquet(eco, nom) if v.version != version]
        trancher = compte.role is Role.ADMIN and f.version.etat is Etat.A_REVOIR
        retirer = compte.role is Role.ADMIN and f.version.etat is Etat.PUBLIEE
        return page(request, "fiche.html", compte, code, fiche=f, sandbox=sandbox, autres=autres,
                    signaux=[(s, _lien_sur(s.preuve.get("url"))) for s in signaux],
                    historique=base.historique(eco, nom, version), trancher=trancher,
                    retirer=retirer, erreur=erreur,
                    publication=etat_publication(f.version.etat, f.raison))

    # --- décision humaine (admin) -------------------------------------------------
    @app.post("/decision")
    def decision(request: Request, ecosysteme: str = Form(...), nom: str = Form(...),
                 version: str = Form(...), decision: str = Form(...), raison: str = Form("")):
        admin = exiger(request, Role.ADMIN)
        try:
            eco, etat = Ecosysteme(ecosysteme), Etat(decision)
        except ValueError:
            raise HTTPException(status_code=400, detail="Décision invalide.")
        raison = raison.strip()[:500]
        # Les refus de pipeline.decision_humaine (B) se disent sur la fiche, pas en erreur 500.
        try:
            decider(base, eco, nom, version, etat, raison, admin.identifiant)
        except KeyError:
            raise HTTPException(status_code=404)
        except ValueError as e:
            return afficher_fiche(request, admin, ecosysteme, nom, version, 400, str(e))
        return RedirectResponse(f"/versions/{eco.value}/{nom}/{version}", status_code=303)

    # --- révocation (admin) ---------------------------------------------------------
    @app.post("/revocation")
    def revocation(request: Request, ecosysteme: str = Form(...), nom: str = Form(...),
                   version: str = Form(...), raison: str = Form("")):
        admin = exiger(request, Role.ADMIN)
        try:
            eco = Ecosysteme(ecosysteme)
        except ValueError:
            raise HTTPException(status_code=404)
        v = base.lire_version(eco, nom, version)
        if v is None:
            raise HTTPException(status_code=404)
        raison = raison.strip()[:500]
        if v.etat is not Etat.PUBLIEE:
            return afficher_fiche(request, admin, ecosysteme, nom, version, 400,
                                  "Révocation refusée : cette version n'est pas publiée.")
        if not raison:
            return afficher_fiche(request, admin, ecosysteme, nom, version, 400,
                                  "Révocation refusée : une raison est obligatoire.")
        # La passerelle d'abord : la version n'est notée révoquée qu'une fois l'archive retirée.
        # Un échec (refus ou panne) la laisse publiée, journalisé, et le bouton reste là.
        try:
            revoquer(eco, nom, version, raison)
        except Exception as e:  # noqa: BLE001 — refus, réseau, ssh : tout se dit sur la fiche
            base.journaliser(admin.identifiant, "revocation_echouee", f"{eco.value}:{nom}@{version}",
                             {"raison": raison, "erreur": str(e)[:300]})
            return afficher_fiche(request, admin, ecosysteme, nom, version, 502,
                                  f"Révocation échouée, la version reste publiée : {e}")
        try:
            base.changer_etat(eco, nom, version, Etat.REVOQUEE, f"{admin.identifiant} : {raison}",
                              acteur=admin.identifiant, attendu=Etat.PUBLIEE)
        except ValueError as e:  # changée pendant l'appel à la passerelle : on n'écrase pas
            base.journaliser(admin.identifiant, "revocation_concurrente",
                             f"{eco.value}:{nom}@{version}", {"raison": raison, "erreur": str(e)})
            return afficher_fiche(request, admin, ecosysteme, nom, version, 409,
                                  f"L'état de la version a changé pendant la révocation ({e}). "
                                  "L'archive a été retirée de la passerelle ; vérifiez la fiche.")
        return RedirectResponse(f"/versions/{eco.value}/{nom}/{version}", status_code=303)

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

    # --- journal (admin) ---------------------------------------------------------
    @app.get("/journal", response_class=HTMLResponse)
    def journal(request: Request, avant: int | None = None, q: str = "", verifier: bool = False):
        # Réservé aux admins : il contient les comptes et les identifiants tapés à la connexion.
        admin = exiger(request, Role.ADMIN)
        q = q.strip()[:100]
        entrees = base.journal_recent(PAGE_JOURNAL, avant=avant, q=q or None)
        verification = None
        if verifier:
            intacte, cassee = base.verifier_journal()
            verification = {"intacte": intacte, "cassee": cassee, "total": base.compter_journal()}
        suivante = entrees[-1].seq if len(entrees) == PAGE_JOURNAL else None
        return page(request, "journal.html", admin, entrees=entrees, q=q, suivante=suivante,
                    verification=verification, fiches={e.seq: _lien_fiche(e.sujet) for e in entrees})

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
        # Cette session-ci reste ouverte ; les autres ont l'ancienne génération (A5).
        request.session["generation"] = base.lire_compte(compte.identifiant).generation
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
    base = Base(os.environ.get("SAS_DB", "sas.db"))
    mdp = os.environ.get("SAS_ADMIN_MOTDEPASSE")
    if not mdp:
        mdp = secrets.token_urlsafe(12)
        print(f"[sas-pme] Si la base est neuve, mot de passe du compte admin : {mdp}",
              file=sys.stderr)
    elif len(mdp) < MDP_MIN and not base.lister_comptes():
        raise RuntimeError(f"SAS_ADMIN_MOTDEPASSE trop court pour le compte admin initial : "
                           f"{MDP_MIN} caractères au moins.")
    secret = os.environ.get("SAS_SECRET") or secrets.token_urlsafe(32)
    intervalle = float(os.environ.get("SAS_TRAITEMENT_INTERVALLE", "60"))
    diffusion = dr.Diffusion()
    return creer_app(base=base, mot_de_passe=mdp, secret=secret,
                     traiter=_traiter_par_defaut(diffusion) if intervalle > 0 else None,
                     intervalle=intervalle, diffusion=diffusion)


def _traiter_par_defaut(diffusion: dr.Diffusion) -> Traiter:
    """Le vrai `pipeline.traitement.traiter` (B), avec le dossier d'archives de SAS_ARCHIVES ;
    chaque étape est dite à la page « Direct »."""
    from plateforme.pipeline.traitement import traiter

    dossier = Path(os.environ.get("SAS_ARCHIVES", "archives"))
    return lambda base: traiter(base, dossier=dossier, suivi=diffusion.publier)


def __getattr__(nom: str):
    # `uvicorn plateforme.web.app:app` : l'application n'est créée qu'à la demande,
    # pour que l'import du module (tests) n'ouvre aucune base.
    if nom == "app":
        globals()["app"] = _depuis_environnement()
        return globals()["app"]
    raise AttributeError(nom)
