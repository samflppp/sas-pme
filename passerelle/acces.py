"""Le journal d'accès de pypiserver, ligne par ligne (A pour C) : ce que les serveurs ont demandé à
la passerelle, pour le panneau « Serveur » de la plateforme.

Mêmes deux formes que l'inventaire (`passerelle.inventaire`) : celle que pypiserver écrit ici
(heure en tête, sans code HTTP) et la forme access classique. Chaque requête garde son numéro de
ligne (`n`, à partir de 1) : la plateforme note où en était le journal au moment d'une demande et ne
montre que la suite. Une ligne non reconnue (démarrage de pypiserver…) est sautée, jamais une erreur.
"""
import re

_FORME_A = re.compile(r'^(?P<a>\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d)(?:[,.]\d+)? (?P<ip>\S+) - - '
                      r'"(?P<methode>[A-Z]+) (?P<chemin>\S+)[^"]*"')
_FORME_B = re.compile(r'^(?P<ip>\S+) - - \[(?P<a>[^\]]+)\] "(?P<methode>[A-Z]+) (?P<chemin>\S+)[^"]*"'
                      r'(?: (?P<code>\d{3}))?')
MAX_LIGNES = 500


def requetes(lignes: list[str], apres: int = 0) -> list[dict]:
    sortie = []
    for n, ligne in enumerate(lignes, start=1):
        if n <= apres:
            continue
        m = _FORME_A.match(ligne) or _FORME_B.match(ligne)
        if m is None:
            continue
        g = m.groupdict()
        sortie.append({"n": n, "a": g["a"], "ip": g["ip"], "methode": g["methode"],
                       "chemin": g["chemin"][:300],
                       "code": int(g["code"]) if g.get("code") else None})
    return sortie[-MAX_LIGNES:]
