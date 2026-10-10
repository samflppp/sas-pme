"""Relais d'API en liste fermée (docs/architecture.md, flux 4), asyncio, bibliothèque standard.

  serveur ──CONNECT──▶ passerelle :3128 ──▶ plateforme :3129 ──▶ API autorisée (Internet)

- Seule la méthode CONNECT est acceptée : le flux TLS passe tel quel, **sans déchiffrement**.
- La **plateforme** décide : domaine dans la liste fermée (`api.github.com`, ou `*.stripe.com` pour
  ses sous-domaines) et port autorisé (443 par défaut), sinon 403.
- La **passerelle** n'a pas Internet : elle transmet la demande à la plateforme (`amont`) et relaie
  sa réponse. Elle peut aussi appliquer une liste (défense en profondeur).
- Chaque demande est journalisée (JSON par ligne) : date UTC, client, hôte, port, décision.

Lancement (variables d'environnement) :
  SAS_RELAIS_ECOUTE   hôte:port d'écoute (plateforme 10.42.1.10:3129, passerelle 10.42.2.10:3128)
  SAS_RELAIS_LISTE    fichier des domaines autorisés (un par ligne, # pour commenter) — plateforme
  SAS_RELAIS_PORTS    ports autorisés, séparés par des virgules (défaut 443)
  SAS_RELAIS_AMONT    hôte:port du relais suivant — passerelle (10.42.1.10:3129)
  SAS_RELAIS_JOURNAL  fichier du journal
  python3 -m passerelle.relais
"""

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

MAX_ENTETE = 8192
DELAI_ENTETE_S = 10
_HOTE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,252})$")


def lire_liste(chemin: Path) -> set[str]:
    domaines = set()
    for ligne in Path(chemin).read_text().splitlines():
        ligne = ligne.split("#", 1)[0].strip().lower()
        if ligne:
            domaines.add(ligne)
    return domaines


def _reponse(code: int, texte: str) -> bytes:
    return f"HTTP/1.1 {code} {texte}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".encode()


async def _copier(lecteur: asyncio.StreamReader, ecrivain: asyncio.StreamWriter) -> None:
    try:
        while donnees := await lecteur.read(65536):
            ecrivain.write(donnees)
            await ecrivain.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        try:
            ecrivain.close()
        except Exception:  # noqa: BLE001
            pass


class Relais:
    def __init__(self, autorises: set[str] | None, ports: set[int] | None, journal: Path | None,
                 amont: tuple[str, int] | None = None):
        self.autorises = {a.lower().rstrip(".") for a in autorises} if autorises is not None else None
        self.ports, self.journal, self.amont = ports, journal, amont

    def autorise(self, hote: str, port: int) -> bool:
        if self.ports is not None and port not in self.ports:
            return False
        if self.autorises is None:
            return True
        h = hote.lower().rstrip(".")
        for a in self.autorises:
            if a.startswith("*."):
                if h.endswith(a[1:]) and len(h) > len(a) - 1:
                    return True
            elif h == a:
                return True
        return False

    def _noter(self, client: str, hote: str, port: int | None, decision: str) -> None:
        if self.journal is None:
            return
        ligne = {"quand": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "client": client, "hote": hote[:255], "port": port, "decision": decision}
        with open(self.journal, "a") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")

    async def _lire_entete(self, lecteur: asyncio.StreamReader) -> tuple[bytes, bytes] | None:
        tampon = b""
        while b"\r\n\r\n" not in tampon:
            if len(tampon) > MAX_ENTETE:
                return None
            bloc = await asyncio.wait_for(lecteur.read(4096), DELAI_ENTETE_S)
            if not bloc:
                return None
            tampon += bloc
        fin = tampon.index(b"\r\n\r\n") + 4
        if fin > MAX_ENTETE:
            return None
        return tampon[:fin], tampon[fin:]

    async def client(self, lecteur: asyncio.StreamReader, ecrivain: asyncio.StreamWriter) -> None:
        pair = ecrivain.get_extra_info("peername")
        ip = pair[0] if pair else "?"
        try:
            lu = await self._lire_entete(lecteur)
        except (asyncio.TimeoutError, ConnectionError):
            lu = None
        if lu is None:
            await self._fermer(ecrivain, _reponse(400, "Bad Request"))
            return
        entete, reste = lu
        morceaux = entete.split(b"\r\n", 1)[0].decode("latin-1").split()
        if len(morceaux) != 3 or morceaux[0] != "CONNECT":
            self._noter(ip, morceaux[1] if len(morceaux) > 1 else "", None, "methode_refusee")
            await self._fermer(ecrivain, _reponse(405, "Method Not Allowed"))
            return
        hote, _, port_txt = morceaux[1].rpartition(":")
        if not (_HOTE.match(hote) and port_txt.isdigit()):
            await self._fermer(ecrivain, _reponse(400, "Bad Request"))
            return
        port = int(port_txt)
        if not self.autorise(hote, port):
            self._noter(ip, hote, port, "refuse")
            await self._fermer(ecrivain, _reponse(403, "Forbidden"))
            return
        try:
            if self.amont:
                l2, e2 = await asyncio.wait_for(asyncio.open_connection(*self.amont), 10)
                e2.write(entete + reste)          # la plateforme décide et répond elle-même
            else:
                l2, e2 = await asyncio.wait_for(asyncio.open_connection(hote, port), 10)
                ecrivain.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
                if reste:
                    e2.write(reste)
            await e2.drain()
            await ecrivain.drain()
        except (OSError, asyncio.TimeoutError):
            self._noter(ip, hote, port, "injoignable")
            await self._fermer(ecrivain, _reponse(502, "Bad Gateway"))
            return
        self._noter(ip, hote, port, "relaye" if self.amont else "autorise")
        await asyncio.gather(_copier(lecteur, e2), _copier(l2, ecrivain))

    @staticmethod
    async def _fermer(ecrivain: asyncio.StreamWriter, reponse: bytes) -> None:
        try:
            ecrivain.write(reponse)
            await ecrivain.drain()
            ecrivain.close()
        except ConnectionError:
            pass


def _adresse(texte: str) -> tuple[str, int]:
    hote, _, port = texte.rpartition(":")
    return hote, int(port)


async def _main() -> None:
    liste = os.environ.get("SAS_RELAIS_LISTE")
    amont = os.environ.get("SAS_RELAIS_AMONT")
    journal = os.environ.get("SAS_RELAIS_JOURNAL")
    r = Relais(autorises=lire_liste(Path(liste)) if liste else None,
               ports={int(p) for p in os.environ.get("SAS_RELAIS_PORTS", "443").split(",")},
               journal=Path(journal) if journal else None,
               amont=_adresse(amont) if amont else None)
    if r.autorises is None and r.amont is None:
        raise SystemExit("relais : ni liste fermée (SAS_RELAIS_LISTE) ni amont (SAS_RELAIS_AMONT)")
    hote, port = _adresse(os.environ.get("SAS_RELAIS_ECOUTE", "127.0.0.1:3129"))
    serveur = await asyncio.start_server(r.client, hote, port)
    async with serveur:
        await serveur.serve_forever()


if __name__ == "__main__":
    asyncio.run(_main())
