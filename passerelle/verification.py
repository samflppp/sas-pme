"""Vérification d'un manifeste reçu par la passerelle (docs/contrats.md § 4, règles de la passerelle).

Ordre : signature (clé publique de la plateforme seulement), âge, nonce, hash de chaque archive.
Le nonce n'est retenu que si tout le reste passe : un refus ne le consomme pas.
"""

import base64
import binascii
import hashlib
from datetime import datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from pydantic import ValidationError

from commun.modeles import Manifeste

AGE_MAX = timedelta(minutes=10)


class Refus(Exception):
    code = 400


class HashDifferent(Refus):
    code = 400


class SignatureInvalide(Refus):
    code = 401


class ManifestePerime(Refus):
    code = 401


class NonceDejaVu(Refus):
    code = 409


def _cle(publique_pem: bytes) -> Ed25519PublicKey:
    cle = load_pem_public_key(publique_pem)
    if not isinstance(cle, Ed25519PublicKey):
        raise ValueError("la clé publique de la plateforme n'est pas Ed25519")
    return cle


def verifier(manifeste: bytes, signature_b64: str, archives: dict[str, bytes], publique_pem: bytes,
             maintenant: datetime, nonces_vus: set[str]) -> Manifeste:
    """Renvoie le manifeste s'il est publiable, lève un `Refus` sinon."""
    try:
        signature = base64.b64decode(signature_b64, validate=True)
        _cle(publique_pem).verify(signature, manifeste)
    except (binascii.Error, ValueError, InvalidSignature) as e:
        raise SignatureInvalide("signature invalide") from e

    try:
        m = Manifeste.model_validate_json(manifeste)
    except ValidationError as e:
        raise HashDifferent("manifeste illisible") from e

    if abs(maintenant - m.emis_le) > AGE_MAX:
        raise ManifestePerime(f"manifeste émis le {m.emis_le.isoformat()}")
    if m.nonce in nonces_vus:
        raise NonceDejaVu("nonce déjà vu")

    attendus = {f.nom: f.sha256 for f in m.fichiers}
    if any("/" in n or "\\" in n or n.startswith(".") for n in attendus):
        raise HashDifferent("nom de fichier interdit")
    if set(archives) != set(attendus):
        raise HashDifferent("archives différentes du manifeste")
    for nom, contenu in archives.items():
        if hashlib.sha256(contenu).hexdigest() != attendus[nom]:
            raise HashDifferent(f"hash différent : {nom}")

    nonces_vus.add(m.nonce)
    return m
