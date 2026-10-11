"""Configuration WireGuard du lien plateforme ↔ passerelle (mode « plateforme hors site », C).

Rendue pour systemd-networkd, présent sur Ubuntu : la passerelle, sans Internet, n'a aucun paquet à
installer. Chaque hôte tire sa clé privée lui-même (installer_wireguard.sh) ; ce rendu ne reçoit que
la clé publique du pair, vérifiée, et ne cite la clé privée que par son chemin.

- La passerelle appelle la plateforme (Endpoint) : elle n'écoute rien de plus, et c'est elle qui
  traverse un NAT si la plateforme est chez un hébergeur.
- AllowedIPs = l'adresse du seul pair : ni route par défaut, ni transit par la plateforme. La
  passerelle reste sans Internet, tunnel monté ou non.

    python3 -I rendre.py <plateforme|passerelle> <clé publique du pair> <dossier de sortie>
"""
import base64
import binascii
import re
import sys
from pathlib import Path

CLE_PRIVEE = "/etc/systemd/network/wg0.key"
PORT = 51820
TUNNEL = {"plateforme": "10.99.0.1", "passerelle": "10.99.0.2"}
ENDPOINT_PLATEFORME = "10.42.1.10"     # IP privée dans le VPC de démo ; l'IP publique hors démo
FICHIERS = ("90-sas-wg0.netdev", "90-sas-wg0.network")


def _cle(cle: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9+/]{43}=", cle):
        raise ValueError("clé publique WireGuard attendue : 32 octets en base64")
    try:
        if len(base64.b64decode(cle, validate=True)) != 32:
            raise ValueError("clé publique WireGuard attendue : 32 octets en base64")
    except binascii.Error as e:
        raise ValueError(f"clé publique illisible : {e}") from e
    return cle


def rendre(role: str, *, cle_pair: str) -> tuple[str, str]:
    """(fichier .netdev, fichier .network) de wg0 pour ce rôle."""
    if role not in TUNNEL:
        raise ValueError(f"rôle inconnu : {role!r} (plateforme ou passerelle)")
    cle_pair = _cle(cle_pair)
    pair = "passerelle" if role == "plateforme" else "plateforme"
    wireguard = [f"PrivateKeyFile={CLE_PRIVEE}"]
    pair_lignes = [f"PublicKey={cle_pair}", f"AllowedIPs={TUNNEL[pair]}/32"]
    if role == "plateforme":
        wireguard.append(f"ListenPort={PORT}")
    else:
        pair_lignes += [f"Endpoint={ENDPOINT_PLATEFORME}:{PORT}", "PersistentKeepalive=25"]
    netdev = "\n".join([
        "# sas-pme : lien unique plateforme <-> passerelle (rendu par infra/wireguard/rendre.py)",
        "[NetDev]", "Name=wg0", "Kind=wireguard", f"Description=sas-pme vers la {pair}", "",
        "[WireGuard]", *wireguard, "",
        "[WireGuardPeer]", *pair_lignes, ""])
    network = "\n".join([
        "[Match]", "Name=wg0", "",
        "[Network]", f"Address={TUNNEL[role]}/24", ""])
    return netdev, network


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__.strip().splitlines()[-1].strip())
    role, cle, dossier = sys.argv[1:]
    for nom, texte in zip(FICHIERS, rendre(role, cle_pair=cle)):
        (Path(dossier) / nom).write_text(texte)
