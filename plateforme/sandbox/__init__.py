"""Sandbox (C). Stub M0 : n'exécute rien et renvoie un rapport vide (docs/contrats.md § 3).

La v1 (M1) lancera un conteneur Docker sans réseau, avec faux DNS/HTTP et leurres.
"""

from pathlib import Path

from commun.modeles import Ecosysteme, RapportSandbox

__all__ = ["Ecosysteme", "RapportSandbox", "executer"]


def executer(
    ecosysteme: Ecosysteme, archive: Path, module: str, duree_max_s: int = 120
) -> RapportSandbox:
    if not Path(archive).is_file():
        raise FileNotFoundError(archive)
    return RapportSandbox(
        requetes_dns=[],
        connexions=[],
        fichiers_sensibles=[],
        leurres_lus=[],
        processus=[],
        code_sortie=0,
        duree_s=0.0,
        delai_depasse=False,
    )
