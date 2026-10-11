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

from commun.modeles import Ecosysteme, Etat, Version
from plateforme.db.acces import Base, EntreeJournal

ETAPES = [
    ("demande", "Demande reçue"),
    ("attente", "Délai de 3 jours après la publication"),
    ("telechargement", "Téléchargement depuis PyPI"),
    ("sandbox", "Sandbox : installation sans réseau réel, avec leurres"),
    ("statique", "Contrôles du nom, du code et des métadonnées"),
    ("ia", "IA locale : lecture et explication"),
    ("politique", "Politique : le code décide"),
    ("publication", "Signature et publication dans la passerelle"),
]
_ANALYSE = [cle for cle, _ in ETAPES[2:]]
# Une étape jamais vue d'une version dans ces états ne viendra plus : elle a été sautée.
_SANS_SUITE = {Etat.BLOQUEE, Etat.PUBLIEE, Etat.REVOQUEE, Etat.A_REVOIR}


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
            detail = f"par {demande_.acteur}, le {demande_.a.strftime('%d/%m à %H:%M')}"
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
