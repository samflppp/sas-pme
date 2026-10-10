"""Politique de décision. M0 : factice, tout approuver. M1 : politique déterministe.

Le code décide ici, jamais le LLM (docs/contexte.md § 6).
"""
from commun.modeles import Etat, Signal, Verdict


def decider(signaux: list[Signal]) -> Verdict:
    return Verdict(etat=Etat.APPROUVEE, raison="Politique factice M0 : tout est approuvé.",
                   signaux=signaux)
