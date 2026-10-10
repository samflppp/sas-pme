"""Boucle de traitement (point H3) : versions en attente mûres → analyse → verdict → publication.

Le code décide (politique), jamais le LLM. Une analyse qui échoue met « à revoir », jamais
« approuvée ». Sans la sandbox ou la signature de C, rien n'est traité.
"""
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from commun.modeles import Etat, RapportSandbox, Version
from plateforme.db.acces import Base
from plateforme.pipeline import politique, pypi

Telecharger = Callable[[str, str, Path], list[Path]]
Executer = Callable[..., RapportSandbox]
Publier = Callable[..., None]


def _telecharger_pypi(nom: str, version: str, dossier: Path) -> list[Path]:
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        return pypi.telecharger(nom, version, dossier, client=client)


def _de_c(module: str, fonction: str):
    """Le vrai module de C ; erreur explicite s'il manque, pour ne jamais approuver sans lui."""
    try:
        return getattr(__import__(f"plateforme.{module}", fromlist=[fonction]), fonction)
    except (ImportError, AttributeError) as e:
        raise RuntimeError(f"{module}.{fonction} (C) indisponible : rien n'est traité") from e


def _archive_a_executer(archives: list[Path]) -> Path:
    roues = [a for a in archives if a.suffix == ".whl"]
    return (roues or archives)[0]


def traiter(base: Base, maintenant: datetime | None = None, *, delai: timedelta = pypi.DELAI,
            dossier: Path = Path("archives"), telecharger: Telecharger | None = None,
            executer: Executer | None = None, publier: Publier | None = None
            ) -> list[tuple[Version, Etat]]:
    """Traite chaque version en attente dont le délai est écoulé ; renvoie (version, état final)."""
    telecharger = telecharger or _telecharger_pypi
    executer = executer or _de_c("sandbox", "executer")
    publier = publier or _de_c("signature", "publier")
    maintenant = maintenant or datetime.now(timezone.utc)
    resultats = []
    for v in base.versions_a_traiter(maintenant, delai):
        cle = (v.ecosysteme, v.nom, v.version)
        base.changer_etat(*cle, Etat.EN_ANALYSE, "analyse en cours")
        try:
            archives = telecharger(v.nom, v.version, dossier / v.nom / v.version)
            rapport = executer(v.ecosysteme, _archive_a_executer(archives),
                               v.nom.replace("-", "_"))
            base.enregistrer_rapport_sandbox(*cle, rapport)
            verdict = politique.decider(signaux=[])
        except Exception as e:  # noqa: BLE001 — une analyse ratée ne doit jamais approuver
            base.changer_etat(*cle, Etat.A_REVOIR, f"analyse impossible : {e}")
            resultats.append((v, Etat.A_REVOIR))
            continue
        verdict_id = base.enregistrer_verdict(*cle, verdict)
        base.changer_etat(*cle, verdict.etat, verdict.raison)
        etat = verdict.etat
        if etat is Etat.APPROUVEE:
            try:
                publier(v.ecosysteme, v.nom, v.version, archives, verdict_id)
                base.changer_etat(*cle, Etat.PUBLIEE, "signée et publiée dans la passerelle")
                etat = Etat.PUBLIEE
            except Exception as e:  # noqa: BLE001 — reste approuvée, à republier
                base.changer_etat(*cle, Etat.APPROUVEE, f"publication échouée : {e}")
        resultats.append((v, etat))
    return resultats
