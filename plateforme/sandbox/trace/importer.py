"""Importe le paquet installé dans /tmp/site, dans le conteneur cible.

`site.addsitedir` traite aussi les fichiers .pth (code exécuté au démarrage de Python, un vecteur
d'attaque connu). Si le module indiqué n'existe pas (nom de distribution ≠ nom d'import, ex. PyYAML
→ yaml), on importe les modules de premier niveau trouvés dans /tmp/site.
"""

import importlib
import os
import site
import sys
import traceback

SITE = "/tmp/site"


def premiers_niveaux() -> list[str]:
    noms = []
    for n in sorted(os.listdir(SITE)):
        if n.endswith((".dist-info", ".egg-info", ".pth")) or n.startswith((".", "_")) or n == "bin":
            continue
        if n.endswith(".py"):
            noms.append(n[:-3])
        elif os.path.isdir(os.path.join(SITE, n)):
            noms.append(n)
    return noms[:10]


def main(module: str) -> int:
    site.addsitedir(SITE)
    try:
        importlib.import_module(module)
        return 0
    except ModuleNotFoundError as e:
        if e.name != module:
            traceback.print_exc()
            return 1
    except BaseException:  # noqa: BLE001 — on note tout ce que fait le paquet, même SystemExit
        traceback.print_exc()
        return 1
    code = 0
    for nom in premiers_niveaux():
        try:
            importlib.import_module(nom)
        except BaseException:  # noqa: BLE001
            traceback.print_exc()
            code = 1
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
