"""Politique de décision déterministe : un signal BLOQUANT bloque, un signal FORT met à revoir.

Le code décide ici, jamais le LLM (docs/contexte.md § 6) : un signal LLM ne peut pas être
BLOQUANT (commun/modeles.py), il peut au plus mettre à revoir.
"""
from commun.modeles import Etat, Niveau, Signal, Verdict


def _resume(signaux: list[Signal]) -> str:
    return " ; ".join(s.preuve.get("extrait") or s.sorte for s in signaux)


def decider(signaux: list[Signal]) -> Verdict:
    bloquants = [s for s in signaux if s.niveau is Niveau.BLOQUANT]
    if bloquants:
        return Verdict(etat=Etat.BLOQUEE, raison=f"Bloquée : {_resume(bloquants)}.",
                       signaux=signaux)
    forts = [s for s in signaux if s.niveau is Niveau.FORT]
    if forts:
        return Verdict(etat=Etat.A_REVOIR, raison=f"À revoir : {_resume(forts)}.",
                       signaux=signaux)
    return Verdict(etat=Etat.APPROUVEE, raison="Aucun signal fort ni bloquant.", signaux=signaux)
