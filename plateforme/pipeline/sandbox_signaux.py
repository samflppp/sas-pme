"""Rapport de sandbox (C) → signaux SANDBOX, par des règles fixes : le code décide.

La sandbox n'a pas de réseau réel : toute requête DNS ou connexion pendant l'installation ou
l'import a été tentée par le paquet. Lire un leurre (faux jeton, faux fichier de clés) est la
preuve d'un vol de secrets : BLOQUANT. Une analyse sabotée (journal réseau noyé, traces effacées)
n'est jamais approuvée : FORT, donc à revoir par un humain.
"""
from pathlib import PurePosixPath

from commun.modeles import Ecosysteme, Niveau, RapportSandbox, Signal, Source
from plateforme.sandbox.rapport import JOURNAL_TRONQUE, TRACES_EFFACEES

EXTRAIT_MAX = 200
_OUTILS = {"sh", "bash", "dash", "zsh", "curl", "wget", "nc", "ncat", "netcat", "socat",
           "telnet", "ssh", "scp", "base64", "powershell", "pwsh"}


def _liste(elements: list[str]) -> str:
    texte = ", ".join(elements)
    return texte if len(texte) <= EXTRAIT_MAX - 40 else texte[:EXTRAIT_MAX - 41] + "…"


def _outil(commande: str) -> str | None:
    mots = commande.split()
    nom = PurePosixPath(mots[0]).name if mots else ""
    return nom if nom in _OUTILS else None


def signaux_sandbox(eco: Ecosysteme, nom: str, version: str, r: RapportSandbox) -> list[Signal]:
    def signal(niveau: Niveau, sorte: str, extrait: str, **preuve) -> Signal:
        return Signal(ecosysteme=eco, nom=nom, version=version, source=Source.SANDBOX,
                      niveau=niveau, sorte=sorte, preuve={"extrait": extrait[:EXTRAIT_MAX], **preuve})

    signaux = []
    if TRACES_EFFACEES in r.processus:
        signaux.append(signal(Niveau.FORT, "traces_effacees",
                              "les traces de la sandbox ont été effacées ou réécrites pendant "
                              "l'analyse : le paquet a pu cacher ce qu'il a fait"))
    if JOURNAL_TRONQUE in r.requetes_dns:
        signaux.append(signal(Niveau.FORT, "journal_tronque",
                              "le paquet a noyé le journal réseau de la sandbox sous un déluge de "
                              "requêtes : la suite n'a pas été vue"))
    requetes = [d for d in r.requetes_dns if d != JOURNAL_TRONQUE]
    if r.leurres_lus:
        signaux.append(signal(Niveau.BLOQUANT, "lit_leurre",
                              f"leurres lus : {_liste(r.leurres_lus)}", leurres=r.leurres_lus))
    if requetes:
        signaux.append(signal(Niveau.FORT, "dns", f"requêtes DNS : {_liste(requetes)}",
                              requetes=requetes))
    if r.connexions:
        signaux.append(signal(Niveau.FORT, "connexion",
                              f"connexions tentées : {_liste(r.connexions)}",
                              connexions=r.connexions))
    if r.fichiers_sensibles:
        signaux.append(signal(Niveau.FORT, "fichier_sensible",
                              f"fichiers sensibles ouverts : {_liste(r.fichiers_sensibles)}",
                              fichiers=r.fichiers_sensibles))
    lances = [p for p in r.processus if _outil(p)]
    if lances:
        signaux.append(signal(Niveau.FORT, "processus", f"processus lancés : {_liste(lances)}",
                              processus=lances))
    if r.delai_depasse:
        signaux.append(signal(Niveau.MOYEN, "delai_depasse",
                              f"toujours actif après {r.duree_s:.0f} s (battement ?)"))
    if r.code_sortie != 0:
        signaux.append(signal(Niveau.INFO, "echec_execution",
                              f"installation ou import en échec (code {r.code_sortie})"))
    return signaux
