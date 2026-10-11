"""Demande d'installation signée (A pour C, conception-demo § 1) : la plateforme demande au serveur
de démo d'installer un paquet ; le serveur ne l'exécute que si elle est signée par la plateforme.

Ce n'est pas un manifeste (`commun.Manifeste`, contrat § 4) : un message à part, signé sur des
octets préfixés (`PREFIXE`), si bien qu'une signature de publication ne vaut jamais demande
d'installation, ni l'inverse. Mêmes règles que les manifestes : clé Ed25519 de la plateforme,
âge de 10 min au plus, nonce vu une seule fois. Le nom suit PEP 508 ; la version n'est pas demandée :
le serveur prend ce que la passerelle sert, c'est-à-dire la dernière version vérifiée.
"""
import base64
import binascii
import json
from datetime import datetime
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from passerelle.verification import (AGE_MAX, HashDifferent, ManifestePerime, NonceDejaVu,
                                     SignatureInvalide, _cle)

PREFIXE = b"sas-pme/installation/v1\n"


class DemandeInstallation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["installation"] = "installation"
    ecosysteme: Literal["pypi"] = "pypi"
    nom: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,213}$")
    demande: int = Field(ge=0)            # n° de la demande sur la plateforme (journal)
    emis_le: datetime
    nonce: str = Field(pattern=r"^[0-9a-f]{32}$")


def texte(d: DemandeInstallation) -> str:
    """JSON canonique : clés triées, sans espaces."""
    return json.dumps(d.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def signer(d: DemandeInstallation, cle: Ed25519PrivateKey) -> tuple[str, str]:
    t = texte(d)
    return t, base64.b64encode(cle.sign(PREFIXE + t.encode())).decode()


def verifier(t: str, signature_b64: str, publique_pem: bytes, maintenant: datetime,
             nonces_vus: set[str]) -> DemandeInstallation:
    """La demande si elle est signée, récente et neuve ; lève un `Refus` sinon. Le nonce n'est
    retenu que si tout le reste passe."""
    try:
        _cle(publique_pem).verify(base64.b64decode(signature_b64, validate=True),
                                  PREFIXE + t.encode())
    except (binascii.Error, ValueError, InvalidSignature) as e:
        raise SignatureInvalide("signature invalide") from e
    try:
        d = DemandeInstallation.model_validate_json(t)
    except ValidationError as e:
        raise HashDifferent("demande illisible ou nom interdit") from e
    if abs(maintenant - d.emis_le) > AGE_MAX:
        raise ManifestePerime(f"demande émise le {d.emis_le.isoformat()}")
    if d.nonce in nonces_vus:
        raise NonceDejaVu("nonce déjà vu")
    nonces_vus.add(d.nonce)
    return d
