"""Clé de signature de la plateforme et signature Ed25519 des manifestes (docs/contrats.md § 4).

La clé privée vit sur la plateforme seulement (fichier en 0600, hors Git) ; la passerelle ne reçoit
que la clé publique, posée à l'installation.
"""

import base64
import hashlib
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from commun.modeles import Ecosysteme, FichierManifeste, Manifeste, canonique

__all__ = ["generer_cle", "charger_cle", "cle_publique_pem", "signer", "manifeste_publication"]


def generer_cle(chemin: Path) -> Ed25519PrivateKey:
    """Crée la clé privée en 0600. Refuse d'écraser une clé existante."""
    cle = Ed25519PrivateKey.generate()
    pem = cle.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())
    fd = os.open(chemin, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    return cle


def charger_cle(chemin: Path) -> Ed25519PrivateKey:
    cle = serialization.load_pem_private_key(Path(chemin).read_bytes(), password=None)
    if not isinstance(cle, Ed25519PrivateKey):
        raise ValueError(f"{chemin} n'est pas une clé Ed25519")
    return cle


def cle_publique_pem(cle: Ed25519PrivateKey) -> bytes:
    return cle.public_key().public_bytes(serialization.Encoding.PEM,
                                         serialization.PublicFormat.SubjectPublicKeyInfo)


def signer(m: Manifeste, cle: Ed25519PrivateKey) -> str:
    """Signature base64 des octets canoniques du manifeste."""
    return base64.b64encode(cle.sign(canonique(m))).decode("ascii")


def _sha256(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def manifeste_publication(ecosysteme: Ecosysteme, nom: str, version: str, archives: list[Path],
                          verdict_id: int, approuve_le: datetime | None = None) -> Manifeste:
    return Manifeste(
        type="publication", ecosysteme=ecosysteme, nom=nom, version=version,
        fichiers=[FichierManifeste(nom=Path(a).name, sha256=_sha256(a)) for a in archives],
        verdict_id=verdict_id, approuve_le=approuve_le,
        emis_le=datetime.now(timezone.utc), nonce=secrets.token_hex(16))
