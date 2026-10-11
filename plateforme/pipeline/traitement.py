"""Boucle de traitement (point H3) : versions en attente mûres → analyse → verdict → publication.

Le code décide (politique), jamais le LLM. Une analyse qui échoue met « à revoir », jamais
« approuvée ». Sans la sandbox ou la signature de C, rien n'est traité.
"""
import sys
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from packaging.version import InvalidVersion, Version as VersionPep440

from commun.modeles import Ecosysteme, Etat, RapportSandbox, Signal, Source, Version
from plateforme.db.acces import Base
from plateforme.pipeline import (
    llm as llm_local, npm, politique, pypi, rag, semver, veille, veille_rss,
)
from plateforme.pipeline.sandbox_signaux import signaux_sandbox
from plateforme.pipeline.statique.code import controler_code
from plateforme.pipeline.statique.meta import controler_metadonnees
from plateforme.pipeline.statique.nom import controler_nom

Telecharger = Callable[[str, str, Path], list[Path]]
Executer = Callable[..., RapportSandbox]
Publier = Callable[..., None]
Veiller = Callable[[Base, datetime], object]
ControlerMeta = Callable[[Version, str | None, datetime], list[Signal]]
Llm = Callable[[Base, Version, list[Signal], RapportSandbox], llm_local.ResultatLLM]


def _telecharger_reseau(eco: Ecosysteme, nom: str, version: str, dossier: Path) -> list[Path]:
    """Depuis le registre de l'écosystème : PyPI ou npm."""
    registre = npm if eco is Ecosysteme.NPM else pypi
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        return registre.telecharger(nom, version, dossier, client=client)


def _ici(dossier: Path, v: Version, version: str) -> Path:
    """Dossier des archives ; npm à part, pour qu'un même nom sur PyPI et npm ne se mélange pas."""
    return (dossier / "npm" if v.ecosysteme is Ecosysteme.NPM else dossier) / v.nom / version


def _module(v: Version) -> str:
    """Ce que la sandbox importe : `require('<nom>')` pour npm, `import <nom_avec_>` pour pip."""
    return v.nom if v.ecosysteme is Ecosysteme.NPM else v.nom.replace("-", "_")


def _meta_reseau(v: Version, precedente: str | None, maintenant: datetime) -> list[Signal]:
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        return controler_metadonnees(v.ecosysteme, v.nom, v.version, precedente=precedente,
                                     maintenant=maintenant, client=client)


def _llm_reseau(base: Base, v: Version, signaux: list[Signal],
                rapport: RapportSandbox) -> llm_local.ResultatLLM:
    # Les cas connus les plus proches (RAG), donnés comme données ; sans index, aucun passage.
    try:
        ix = rag.ouvrir()
    except Exception:  # noqa: BLE001 — index illisible : journalisé comme absent
        ix = None
    passages = rag.passages(base, v, signaux, rapport, ix)
    with httpx.Client(timeout=300) as client:   # CPU : jusqu'à quelques dizaines de secondes
        return llm_local.analyser(base, v, signaux, rapport, client=client, url=llm_local.url(),
                                  modele=llm_local.modele(), passages=passages)


def _pep(version: str) -> VersionPep440 | None:
    try:
        return VersionPep440(version)
    except InvalidVersion:
        return None


def _ordre(v: Version, version: str):
    """Clé de comparaison : semver pour npm, PEP 440 pour PyPI ; None si illisible."""
    if v.ecosysteme is Ecosysteme.NPM:
        return semver.cle(version) if semver.lire(version) else None
    return _pep(version)


def _precedente(base: Base, v: Version) -> str | None:
    """La plus haute version publiée (ou approuvée) plus basse que `v` : la référence du diff."""
    courante = _ordre(v, v.version)
    if courante is None:
        return None
    avant = [(o, x.version) for x in base.versions_du_paquet(v.ecosysteme, v.nom)
             if x.etat in (Etat.PUBLIEE, Etat.APPROUVEE) and (o := _ordre(v, x.version))
             and o < courante]
    return max(avant)[1] if avant else None


def _veiller_reseau(base: Base, maintenant: datetime) -> None:
    """PyPI et OSV, puis les flux RSS ; une panne de l'une n'empêche pas l'autre."""
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        try:
            veille.veiller(base, maintenant, client=client)
        except Exception as e:  # noqa: BLE001 — les flux RSS sont lus quand même
            print(f"[sas-pme] veille : {e!r}", file=sys.stderr)
        veille_rss.veiller_articles(base, maintenant, client=client, flux=veille_rss.flux())


def _de_c(module: str, fonction: str):
    """Le vrai module de C ; erreur explicite s'il manque, pour ne jamais approuver sans lui."""
    try:
        return getattr(__import__(f"plateforme.{module}", fromlist=[fonction]), fonction)
    except (ImportError, AttributeError) as e:
        raise RuntimeError(f"{module}.{fonction} (C) indisponible : rien n'est traité") from e


def _archive_a_executer(archives: list[Path]) -> Path:
    roues = [a for a in archives if a.suffix == ".whl"]
    return (roues or archives)[0]


def _publier(base: Base, v: Version, archives: list[Path], verdict_id: int,
             publier: Publier) -> Etat:
    """Publie ; en cas d'échec, reste approuvée (retentée au tour suivant), sans répéter le journal."""
    cle = (v.ecosysteme, v.nom, v.version)
    try:
        publier(v.ecosysteme, v.nom, v.version, archives, verdict_id)
    except Exception as e:  # noqa: BLE001 — reste approuvée, à republier
        raison = f"publication échouée : {e}"
        if base.fiche(*cle).raison != raison:
            base.changer_etat(*cle, Etat.APPROUVEE, raison)
        return Etat.APPROUVEE
    base.changer_etat(*cle, Etat.PUBLIEE, "signée et publiée dans la passerelle")
    return Etat.PUBLIEE


def traiter(base: Base, maintenant: datetime | None = None, *, delai: timedelta | None = None,
            dossier: Path = Path("archives"), telecharger: Telecharger | None = None,
            executer: Executer | None = None, publier: Publier | None = None,
            veiller: Veiller | None = None, controler_meta: ControlerMeta | None = None,
            llm: Llm | None = None) -> list[tuple[Version, Etat]]:
    """Fait un tour de veille, republie les approuvées non publiées, puis traite chaque version en attente dont le délai est
    écoulé ; renvoie (version, état final). Fait pour être appelée en boucle (tâche de fond de A)."""

    def charger(v: Version, ici: Path) -> list[Path]:
        if telecharger is not None:            # injecté (tests, mesure)
            return telecharger(v.nom, v.version, ici)
        return _telecharger_reseau(v.ecosysteme, v.nom, v.version, ici)
    controler_meta = controler_meta or _meta_reseau
    llm = llm or _llm_reseau
    executer = executer or _de_c("sandbox", "executer")
    publier = publier or _de_c("signature", "publier")
    maintenant = maintenant or datetime.now(timezone.utc)
    delai = pypi.delai() if delai is None else delai
    # La veille d'abord : nouvelles versions en attente, versions retirées ou malveillantes bloquées.
    try:
        (veiller or _veiller_reseau)(base, maintenant)
    except Exception as e:  # noqa: BLE001 — sans veille ce tour-ci, l'analyse continue
        print(f"[sas-pme] veille : {e!r}", file=sys.stderr)
    resultats = []
    # D'abord, les versions approuvées pas encore publiées (passerelle injoignable au tour d'avant).
    # Les archives vérifiées à l'analyse sont reprises : pas de nouveau téléchargement à chaque tour.
    for v in base.lister_versions(Etat.APPROUVEE):
        cle = (v.ecosysteme, v.nom, v.version)
        fiche = base.fiche(*cle)
        if fiche.verdict_id is None:
            continue
        ici = _ici(dossier, v, v.version)
        archives = sorted(ici.iterdir()) if ici.is_dir() else []
        if not archives:
            try:
                archives = charger(v, ici)
            except Exception as e:  # noqa: BLE001 — reste approuvée, retentée au tour suivant
                raison = f"téléchargement pour publication échoué : {e}"
                if fiche.raison != raison:
                    base.changer_etat(*cle, Etat.APPROUVEE, raison)
                continue
        resultats.append((v, _publier(base, v, archives, fiche.verdict_id, publier)))
    for v in base.versions_a_traiter(maintenant, delai):
        cle = (v.ecosysteme, v.nom, v.version)
        base.changer_etat(*cle, Etat.EN_ANALYSE, "analyse en cours")
        try:
            archives = charger(v, _ici(dossier, v, v.version))
            rapport = executer(v.ecosysteme, _archive_a_executer(archives), _module(v))
            base.enregistrer_rapport_sandbox(*cle, rapport)
            precedente = _precedente(base, v)
            ici = _ici(dossier, v, precedente) if precedente else None
            # Les signaux de la veille écrits pendant l'attente (articles) : déjà en base.
            deja = [s for s in base.fiche(*cle).signaux if s.source is Source.VEILLE]
            signaux = [*controler_nom(v.ecosysteme, v.nom, v.version),
                       *controler_code(v.ecosysteme, v.nom, v.version, archives,
                                       precedentes=sorted(ici.iterdir())
                                       if ici and ici.is_dir() else None),
                       *controler_meta(v, precedente, maintenant),
                       *signaux_sandbox(v.ecosysteme, v.nom, v.version, rapport)]
            # Le LLM alerte et explique ; ses signaux (au plus FORT) passent par la politique.
            avis = llm(base, v, [*deja, *signaux], rapport)
            signaux += avis.signaux
            for s in signaux:
                base.ajouter_signal(s)
            verdict = politique.decider([*deja, *signaux]).model_copy(
                update={"explication_llm": avis.explication, "refs_rag": avis.refs_rag})
        except Exception as e:  # noqa: BLE001 — une analyse ratée ne doit jamais approuver
            base.changer_etat(*cle, Etat.A_REVOIR, f"analyse impossible : {e}")
            resultats.append((v, Etat.A_REVOIR))
            continue
        verdict_id = base.enregistrer_verdict(*cle, verdict)
        base.changer_etat(*cle, verdict.etat, verdict.raison)
        etat = verdict.etat
        if etat is Etat.APPROUVEE:
            etat = _publier(base, v, archives, verdict_id, publier)
        resultats.append((v, etat))
    return resultats
