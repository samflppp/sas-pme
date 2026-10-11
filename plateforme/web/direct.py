"""Page « Direct » (A, conception-demo § 1) : où en est chaque version d'une demande.

Deux sources, dans cet ordre :
- la `Diffusion`, en mémoire : ce que la pipeline dit pendant qu'elle travaille (début d'étape,
  explication du LLM mot à mot) ; perdue au redémarrage, et c'est voulu ;
- le journal chaîné : les étapes finies (action `etape`, module pipeline.suivi), la demande et sa
  résolution. Une page rechargée, ou une autre instance, retrouve tout ce qui est fini.
"""
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from packaging.utils import (InvalidSdistFilename, InvalidWheelFilename, canonicalize_name,
                             parse_sdist_filename, parse_wheel_filename)
from packaging.version import InvalidVersion, Version as VersionPep440

from commun.modeles import Ecosysteme, Etat, Version
from plateforme.db.acces import Base, EntreeJournal

ETAPES = [
    ("demande", "Demande reçue"),
    ("attente", "Délai de 3 jours après la publication"),
    ("telechargement", "Téléchargement depuis le registre public (PyPI ou npm)"),
    ("sandbox", "Sandbox : installation sans réseau réel, avec leurres"),
    ("statique", "Contrôles du nom, du code et des métadonnées"),
    ("ia", "IA locale : lecture et explication"),
    ("politique", "Politique : le code décide"),
    ("publication", "Signature et publication dans la passerelle"),
]
_ANALYSE = [cle for cle, _ in ETAPES[2:]]
# Une étape jamais vue d'une version dans ces états ne viendra plus : elle a été sautée.
_SANS_SUITE = {Etat.BLOQUEE, Etat.PUBLIEE, Etat.REVOQUEE, Etat.A_REVOIR}
_ISSUE = {Etat.A_REVOIR: "revoir", Etat.BLOQUEE: "bloque"}   # couleur de la dernière étape franchie


class Diffusion:
    """Ce que dit la pipeline, par sujet (« pypi:nom@version ») ; appelée depuis son fil."""

    def __init__(self):
        self._verrou = threading.Lock()
        self._sujets: dict[str, dict] = {}
        self.seq = 0                              # change à chaque nouvelle : le flux s'y réveille

    def publier(self, sujet: str, etape: str, etat: str, detail: dict) -> None:
        with self._verrou:
            if etape == "telechargement" and etat == "debut":
                self._sujets.pop(sujet, None)       # une nouvelle analyse repart de zéro
            s = self._sujets.setdefault(sujet, {"etapes": {}, "ia": ""})
            if etat == "flux":
                s["ia"] = str(detail.get("explication", ""))
            else:
                s["etapes"][etape] = {"etat": etat, "detail": dict(detail)}
            self.seq += 1

    def vue(self, sujet: str) -> dict:
        with self._verrou:
            s = self._sujets.get(sujet, {"etapes": {}, "ia": ""})
            return {"etapes": {k: dict(v) for k, v in s["etapes"].items()}, "ia": s["ia"]}


@dataclass(frozen=True)
class Demande:
    seq: int
    a: datetime
    acteur: str
    ecosysteme: Ecosysteme
    nom: str
    sujets: list[str]


def demande(e: EntreeJournal) -> Demande | None:
    if e.action != "demande_resolue":
        return None
    eco, _, nom = e.sujet.partition(":")
    return Demande(e.seq, e.a, e.acteur, Ecosysteme(eco), nom, list(e.charge.get("versions", [])))


def _sujet(v: Version) -> str:
    return f"{v.ecosysteme.value}:{v.nom}@{v.version}"


def _decouper(sujet: str) -> tuple[Ecosysteme, str, str] | None:
    eco, _, reste = sujet.partition(":")
    nom, _, version = reste.rpartition("@")
    try:
        return Ecosysteme(eco), nom, version
    except ValueError:
        return None


def duree_courte(s: float | None) -> str:
    if s is None:
        return ""
    if s < 60:
        return f"{s:.1f} s".replace(".", ",")
    return f"{int(s // 60)} min {int(s % 60):02d} s"


def _texte_detail(cle: str, etat: str, d: dict) -> str:
    """Une phrase par étape finie : ce qui a été fait, en clair."""
    if etat == "erreur":
        return d.get("erreur", "erreur")
    if etat != "fin":
        return ""
    if cle == "telechargement":
        n = len(d.get("archives", []))
        return f"{n} archive{'s' if n > 1 else ''} : {', '.join(d.get('archives', []))}"
    if cle == "sandbox":
        vus = [f"{len(d.get(k, []))} {mot}" for k, mot in
               (("dns", "requête(s) DNS"), ("connexions", "connexion(s)"),
                ("leurres", "leurre(s) lu(s)"), ("fichiers", "fichier(s) sensible(s)"))]
        return ", ".join(vus)
    if cle in ("statique", "ia") and "signaux" in d:
        s = d["signaux"]
        if not s:
            return "aucun signal"
        return f"{len(s)} signal(aux) : " + ", ".join(f"{x['sorte']} ({x['niveau']})" for x in s[:4])
    if cle == "politique":
        return f"{d.get('verdict', '')} : {d.get('raison', '')}"
    if cle == "publication":
        return "publiée, signée Ed25519" if d.get("resultat") == "publiee" else \
            "approuvée, publication à retenter"
    return ""


def suivi_version(base: Base, diffusion: Diffusion, v: Version, demande_: Demande,
                  maintenant: datetime, delai: timedelta | None,
                  libelle: Callable[[Etat], str], duree: Callable[[timedelta], str]) -> dict:
    sujet = _sujet(v)
    memoire = diffusion.vue(sujet)
    journal: dict[str, dict] = {}
    for e in base.historique(v.ecosysteme, v.nom, v.version):
        if e.action == "etape":
            if e.charge.get("etape") == "telechargement":
                journal = {}                        # une nouvelle analyse : on garde la dernière
            journal[e.charge.get("etape", "")] = {"etat": e.charge.get("etat"), "detail": e.charge}
    sortie = []
    for cle, titre in ETAPES:
        etat, detail, temps, texte = "a_venir", "", "", ""
        if cle == "demande":
            etat = "fait"
            detail = f"par {demande_.acteur}, le {demande_.a.astimezone().strftime('%d/%m à %H:%M')}"
        elif cle == "attente":
            fin = v.publiee_le + delai if delai is not None else None
            if v.etat not in (Etat.NOUVELLE, Etat.EN_ATTENTE) or (fin and fin <= maintenant):
                etat = "fait"
                detail = f"version publiée sur Internet le {v.publiee_le.strftime('%d/%m/%Y')}"
            else:
                etat = "en_cours"
                detail = f"encore {duree(fin - maintenant)}" if fin else "délai illisible"
        else:
            vu = memoire["etapes"].get(cle) or journal.get(cle)
            if vu is not None:
                d = vu["detail"]
                etat = {"debut": "en_cours", "fin": "fait", "erreur": "erreur"}.get(vu["etat"],
                                                                                   "a_venir")
                temps = duree_courte(d.get("duree_s"))
                detail = _texte_detail(cle, vu["etat"], d)
                if cle == "ia":
                    texte = memoire["ia"] if etat == "en_cours" else d.get("explication", "")
            elif v.etat in _SANS_SUITE:
                etat = "saute"                      # décidée sans cette étape (veille, humain)
        sortie.append({"cle": cle, "titre": titre, "etat": etat, "detail": detail,
                       "duree": temps, "texte": texte})
    # La dernière étape franchie porte le verdict : orange si à revoir, rouge si bloquée.
    if (issue := _ISSUE.get(v.etat)) is not None:
        franchies = [e for e in sortie if e["etat"] in ("fait", "erreur")]
        if franchies:
            franchies[-1]["etat"] = issue
    return {"sujet": sujet, "nom": v.nom, "version": v.version, "etat": v.etat.value,
            "libelle": libelle(v.etat), "etapes": sortie,
            "lien": f"/catalogue/{v.ecosysteme.value}/{v.nom}/-/{v.version}"}


def instantane(base: Base, diffusion: Diffusion, d: Demande, maintenant: datetime,
               delai: timedelta | None, libelle: Callable[[Etat], str],
               duree: Callable[[timedelta], str]) -> dict:
    versions = []
    for sujet in d.sujets:
        cle = _decouper(sujet)
        v = base.lire_version(*cle) if cle else None
        if v is not None:
            versions.append(suivi_version(base, diffusion, v, d, maintenant, delai, libelle, duree))
    return {"demande": d.seq, "paquet": f"{d.ecosysteme.value}:{d.nom}", "nom": d.nom,
            "par": d.acteur, "a": d.a.isoformat(), "versions": versions}


# --- panneau Serveur ---------------------------------------------------------------------------
MAX_LIGNES_SERVEUR = 60


def _archive(chemin: str) -> tuple[str, str] | None:
    """(nom normalisé, version) d'un téléchargement d'archive, sinon None."""
    if not chemin.startswith("/packages/"):
        return None
    fichier = chemin.rsplit("/", 1)[-1]
    try:
        if fichier.endswith(".whl"):
            nom, version, *_ = parse_wheel_filename(fichier)
        else:
            nom, version = parse_sdist_filename(fichier)
    except (InvalidWheelFilename, InvalidSdistFilename, InvalidVersion):
        return None
    return canonicalize_name(nom), str(version)


def _pep(v: str):
    try:
        return VersionPep440(v)
    except InvalidVersion:
        return None


def serveur(base: Base, d: Demande, installation: EntreeJournal | None,
            suivante: EntreeJournal | None, lire_acces, maintenant: datetime,
            delai: timedelta | None, libelle: Callable[[Etat], str],
            duree: Callable[[timedelta], str], index: str, registre: str = "") -> dict:
    """Heures à l'heure locale de la plateforme, comme le journal de pypiserver (asctime) sur la
    passerelle : les deux machines sont réglées pareil (UTC sur AWS).
    Ce que le serveur a demandé à la passerelle depuis l'envoi de cette demande (lignes du
    journal d'accès entre cette installation et la suivante), la version qu'il a reçue, et la
    version amont qui n'est pas (encore) servie. Rien n'est inventé : une ligne absente du
    journal n'est pas montrée."""
    if lire_acces is None:
        return {"configure": False}
    if d.ecosysteme is Ecosysteme.NPM:
        # L'agent du serveur de démo n'installe que pip : la commande npm se tape à la main, vers
        # le registre de la passerelle (Verdaccio sans source amont). Rien n'est lu ni inventé.
        return {"configure": True, "index": registre, "repli": "registry.npmjs.org",
                "commande": f"npm install {d.nom}", "manuel": True, "demandee_a": None,
                "erreur": None, "lignes": [], "installee": None, "amont": None,
                "aucune_servie": False}
    sortie = {"configure": True, "index": index, "repli": "pypi.org", "manuel": False,
              "commande": f"pip install {d.nom}",
              "demandee_a": None, "erreur": None, "lignes": [], "installee": None, "amont": None,
              "aucune_servie": False}
    if installation is None:
        return sortie
    sortie["demandee_a"] = installation.a.astimezone().strftime("%H:%M:%S")
    if installation.action == "installation_echouee":
        sortie["erreur"] = installation.charge.get("erreur", "refusée")
        return sortie
    depuis = int(installation.charge.get("acces_depuis", 0))
    jusqua = int(suivante.charge.get("acces_depuis", 0)) if suivante else None
    try:
        lignes = lire_acces(depuis)["lignes"]
    except Exception as e:  # noqa: BLE001 — passerelle injoignable : on le dit, sans rien inventer
        sortie["erreur"] = f"journal d'accès illisible : {type(e).__name__} {e}"[:300]
        return sortie
    canon = canonicalize_name(d.nom)
    index_lu = False
    for x in lignes:
        if jusqua is not None and x["n"] > jusqua:
            break
        heure = str(x.get("a", ""))[-8:]
        sortie["lignes"].append({"a": heure, "ip": x.get("ip", ""),
                                 "texte": f"{x.get('methode', '')} {x.get('chemin', '')}"})
        if str(x.get("chemin", "")).rstrip("/") == f"/simple/{canon}":
            index_lu = True
        if (a := _archive(str(x.get("chemin", "")))) and a[0] == canon:
            sortie["installee"] = a[1]
    sortie["lignes"] = sortie["lignes"][-MAX_LIGNES_SERVEUR:]
    # La plus récente connue de la plateforme, si elle n'est pas ce que le serveur a reçu.
    versions = [v for v in base.versions_du_paquet(d.ecosysteme, d.nom) if _pep(v.version)]
    # Le serveur a lu l'index, et la plateforme n'a publié aucune version : pip n'a rien à prendre.
    sortie["aucune_servie"] = (index_lu and sortie["installee"] is None
                               and not any(v.etat is Etat.PUBLIEE for v in versions))
    if versions:
        recente = max(versions, key=lambda v: _pep(v.version))
        recue = _pep(sortie["installee"]) if sortie["installee"] else None
        if recente.etat is not Etat.PUBLIEE and (recue is None or _pep(recente.version) > recue):
            detail = {Etat.EN_ANALYSE: "en cours d'analyse", Etat.A_REVOIR: "attend la décision d'un humain",
                      Etat.BLOQUEE: "jamais servie", Etat.REVOQUEE: "retirée de la passerelle",
                      Etat.APPROUVEE: "approuvée, publication en cours"}.get(recente.etat, "")
            if recente.etat in (Etat.NOUVELLE, Etat.EN_ATTENTE) and delai is not None:
                fin = recente.publiee_le + delai
                detail = f"encore {duree(fin - maintenant)} avant l'analyse" if fin > maintenant \
                    else "analyse au prochain tour"
            sortie["amont"] = {"version": recente.version, "etat": recente.etat.value,
                               "libelle": libelle(recente.etat), "detail": detail}
    return sortie
