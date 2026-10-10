"""Faux DNS et faux serveurs TCP/HTTP de la sandbox (docs/architecture.md § 5). Bibliothèque standard
seulement : ce fichier tourne tel quel dans son propre conteneur, sur le réseau Docker interne.

Toute requête DNS reçoit l'IP du piège ; toute connexion TCP sur un port écouté est acceptée, ses
premiers octets sont notés, puis elle reçoit « 200 OK ». Rien ne sort : le réseau n'a pas de route.
Le journal du piège est hors de portée du paquet analysé : c'est la preuve qu'il ne peut pas effacer.

  python piege.py /journal/reseau.jsonl
"""

import json
import socket
import struct
import sys
import threading

PORTS_TCP = (21, 22, 25, 80, 443, 1337, 4444, 5000, 6667, 8000, 8080, 8443, 9001)
MAX_OCTETS = 4096


def nom_demande(paquet: bytes) -> tuple[str, int] | None:
    """(nom, type) de la première question d'une requête DNS, ou None si illisible."""
    try:
        i, etiquettes = 12, []
        while paquet[i]:
            n = paquet[i]
            etiquettes.append(paquet[i + 1:i + 1 + n].decode("ascii", "replace"))
            i += 1 + n
        qtype = struct.unpack(">H", paquet[i + 1:i + 3])[0]
        return ".".join(etiquettes), qtype
    except (IndexError, struct.error):
        return None


def reponse_dns(paquet: bytes, ip: str) -> bytes:
    """Répond à la question : un enregistrement A vers `ip` ; rien pour les autres types."""
    ident = paquet[:2]
    fin_question = paquet.index(b"\0", 12) + 5
    question = paquet[12:fin_question]
    qtype = struct.unpack(">H", paquet[fin_question - 4:fin_question - 2])[0]
    reponses = b""
    if qtype == 1:
        reponses = b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 60, 4) + socket.inet_aton(ip)
    entete = ident + struct.pack(">HHHHH", 0x8180, 1, 1 if reponses else 0, 0, 0)
    return entete + question + reponses


def hote_http(debut: bytes) -> str | None:
    for ligne in debut.split(b"\r\n")[1:]:
        if ligne.lower().startswith(b"host:"):
            return ligne[5:].strip().decode("ascii", "replace").split(":")[0]
    return None


class Journal:
    def __init__(self, chemin: str):
        self._f = open(chemin, "a", buffering=1)
        self._verrou = threading.Lock()

    def ecrire(self, **e) -> None:
        with self._verrou:
            self._f.write(json.dumps(e, ensure_ascii=False) + "\n")


NOMS_LOCAUX = ("localhost", "ip6-localhost", "ip6-loopback")


def noter_dns(journal: Journal, nom: str, qtype: int) -> None:
    """Les noms locaux ne sont pas notés : un déluge de `localhost` ne peut pas noyer la vraie
    fuite (B, C1)."""
    if nom.rstrip(".").lower() in NOMS_LOCAUX:
        return
    journal.ecrire(t="dns", nom=nom, type=qtype)


def _dns(journal: Journal, ip: str) -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", 53))
    while True:
        paquet, client = s.recvfrom(512)
        question = nom_demande(paquet)
        if question is None:
            continue
        noter_dns(journal, question[0], question[1])
        try:
            s.sendto(reponse_dns(paquet, ip), client)
        except (ValueError, struct.error):
            pass


def _client_tcp(journal: Journal, c: socket.socket, port: int) -> None:
    with c:
        c.settimeout(3)
        debut = b""
        try:
            while len(debut) < MAX_OCTETS and b"\r\n\r\n" not in debut:
                bloc = c.recv(1024)
                if not bloc:
                    break
                debut += bloc
        except OSError:
            pass
        journal.ecrire(t="tcp", port=port, hote=hote_http(debut),
                       debut=debut[:MAX_OCTETS].decode("latin-1"))
        try:
            c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK")
        except OSError:
            pass


def _tcp(journal: Journal, port: int) -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(64)
    while True:
        c, _ = s.accept()
        threading.Thread(target=_client_tcp, args=(journal, c, port), daemon=True).start()


def main(chemin: str) -> None:
    journal = Journal(chemin)
    ip = socket.gethostbyname(socket.gethostname())
    for port in PORTS_TCP:
        threading.Thread(target=_tcp, args=(journal, port), daemon=True).start()
    journal.ecrire(t="pret", ip=ip)
    _dns(journal, ip)


if __name__ == "__main__":
    main(sys.argv[1])
