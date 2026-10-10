"""Traceur de la sandbox, chargé par Python au démarrage dans le conteneur (PYTHONPATH).

Un « audit hook » (PEP 578) note les fichiers ouverts, les processus lancés, les résolutions DNS et
les connexions, en JSON par ligne, dans le fichier désigné par SAS_TRACE. Sans SAS_TRACE : rien.
Limite connue (v1) : du code natif peut contourner ce traceur ; la v2 ajoute `strace`, et le journal
du piège réseau, hors de portée du paquet, reste la preuve qui ne s'efface pas.
"""

import os
import sys


def _installer(chemin: str) -> None:
    import json

    fd = os.open(chemin, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o666)
    ignores = tuple({sys.prefix, sys.base_prefix, "/usr/lib/python3", "/usr/local/lib/python3"})
    occupe = [False]
    restant = [20000]

    def noter(e: str, v: str) -> None:
        if restant[0] <= 0:
            return
        restant[0] -= 1
        os.write(fd, (json.dumps({"e": e, "v": v[:500]}) + "\n").encode())

    def crochet(evenement: str, args: tuple) -> None:
        if occupe[0]:
            return
        occupe[0] = True
        try:
            if evenement == "open":
                chemin = args[0]
                if isinstance(chemin, bytes):
                    chemin = os.fsdecode(chemin)
                if isinstance(chemin, str) and not chemin.startswith(ignores):
                    noter("open", chemin)
            elif evenement == "subprocess.Popen":
                a = args[1]
                noter("processus", " ".join(map(str, a)) if isinstance(a, (list, tuple)) else str(a))
            elif evenement == "os.system":
                noter("processus", str(args[0]))
            elif evenement in ("os.exec", "os.posix_spawn"):
                noter("processus", " ".join(map(str, args[1])))
            elif evenement == "socket.getaddrinfo":
                noter("dns", f"{args[0]}:{args[1]}")
            elif evenement == "socket.connect":
                adresse = args[1]
                if isinstance(adresse, tuple) and len(adresse) >= 2:
                    noter("connect", f"{adresse[0]}:{adresse[1]}")
        except Exception:  # noqa: BLE001 — le traceur ne doit jamais faire tomber le paquet
            pass
        finally:
            occupe[0] = False

    sys.addaudithook(crochet)


if os.environ.get("SAS_TRACE"):
    _installer(os.environ["SAS_TRACE"])
