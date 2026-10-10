"""Boucle de traitement (point H3) : versions en attente mûres → analyse → verdict → publication.

Le code décide (politique), jamais le LLM. Une analyse qui échoue met « à revoir », jamais
« approuvée ». Sans la sandbox ou la signature de C, rien n'est traité.
"""
import sys
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from commun.modeles import Etat, RapportSandbox, Version
from plateforme.db.acces import Base
from plateforme.pipeline import politique, pypi, veille
from plateforme.pipeline.statique.nom import controler_nom

Telecharger = Callable[[str, str, Path], list[Path]]
Executer = Callable[..., RapportSandbox]
Publier = Callable[..., None]
Veiller = Callable[[Base, datetime], object]


def _telecharger_pypi(nom: str, version: str, dossier: Path) -> list[Path]:
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        return pypi.telecharger(nom, version, dossier, client=client)


def _veiller_reseau(base: Base, maintenant: datetime) -> None:
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        veille.veiller(base, maintenant, client=client)


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
            veiller: Veiller | None = None) -> list[tuple[Version, Etat]]:
    """Fait un tour de veille, republie les approuvées non publiées, puis traite chaque version en attente dont le délai est
    écoulé ; renvoie (version, état final). Fait pour être appelée en boucle (tâche de fond de A)."""
    telecharger = telecharger or _telecharger_pypi
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
        ici = dossier / v.nom / v.version
        archives = sorted(ici.iterdir()) if ici.is_dir() else []
        if not archives:
            try:
                archives = telecharger(v.nom, v.version, ici)
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
            archives = telecharger(v.nom, v.version, dossier / v.nom / v.version)
            rapport = executer(v.ecosysteme, _archive_a_executer(archives),
                               v.nom.replace("-", "_"))
            base.enregistrer_rapport_sandbox(*cle, rapport)
            signaux = controler_nom(v.ecosysteme, v.nom, v.version)
            for s in signaux:
                base.ajouter_signal(s)
            verdict = politique.decider(signaux)
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
