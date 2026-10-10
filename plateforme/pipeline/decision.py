"""pipeline.decision_humaine (docs/contrats.md § 5) : un admin approuve ou bloque une version
« à revoir ». Le web de A ne l'appelle que pour un admin.

La décision devient un signal HUMAIN, puis la politique décide avec tous les signaux de la
version : un humain lève un signal FORT, jamais un signal BLOQUANT. Une version approuvée est
publiée au tour suivant de `traiter()` (archives déjà vérifiées).
"""
from commun.modeles import Ecosysteme, Etat, Niveau, Signal, Source, Verdict
from plateforme.db.acces import Base
from plateforme.pipeline import politique

_SORTES = {Etat.APPROUVEE: (politique.APPROBATION, Niveau.INFO),
           Etat.BLOQUEE: ("blocage_humain", Niveau.BLOQUANT)}


def decision_humaine(base: Base, eco: Ecosysteme | str, nom: str, version: str,
                     etat: Etat | str, raison: str, acteur: str) -> Verdict:
    """Lève ValueError (décision, raison ou état invalides), KeyError (version inconnue)."""
    eco, etat = Ecosysteme(eco), Etat(etat)
    if etat not in _SORTES:
        raise ValueError(f"décision impossible : {etat} (approuvee ou bloquee seulement)")
    if not raison.strip():
        raise ValueError("une raison est obligatoire pour une décision humaine")
    fiche = base.fiche(eco, nom, version)
    if fiche is None:
        raise KeyError((eco, nom, version))
    if fiche.version.etat is not Etat.A_REVOIR:
        raise ValueError(f"{nom} {version} n'est pas « à revoir » ({fiche.version.etat})")
    sorte, niveau = _SORTES[etat]
    s = Signal(ecosysteme=eco, nom=nom, version=version, source=Source.HUMAIN, niveau=niveau,
               sorte=sorte, preuve={"extrait": f"{acteur} : {raison.strip()}", "acteur": acteur})
    base.ajouter_signal(s)
    verdict = politique.decider([*fiche.signaux, s])
    base.enregistrer_verdict(eco, nom, version, verdict, acteur=acteur)
    # Une autre décision a pu passer depuis la lecture de la fiche : refusée, pas écrasée (A4).
    base.changer_etat(eco, nom, version, verdict.etat, verdict.raison, acteur=acteur,
                      attendu=Etat.A_REVOIR)
    return verdict
