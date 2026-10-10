"""Signature et publication vers la passerelle (C), docs/contrats.md § 4.

M1 (si SAS_PASSERELLE_URL est posée) : manifeste signé Ed25519, POST au récepteur en TLS mutuel.
  SAS_PASSERELLE_URL    ex. https://10.42.2.10:8443
  SAS_CLE_SIGNATURE     clé privée Ed25519 de la plateforme (PEM, 0600)
  SAS_TLS_CA            autorité qui a signé le certificat de la passerelle
  SAS_TLS_CERT, SAS_TLS_CLE   certificat client de la plateforme et sa clé

Stub M0 (sinon) : aucune signature, les archives sont copiées par scp dans le dépôt de pypiserver.
  SAS_PASSERELLE_SSH    utilisateur@ip de la passerelle, ex. ubuntu@10.42.2.10
  SAS_PASSERELLE_DEPOT  dossier servi par pypiserver (défaut /srv/pypi/packages)
  SAS_PASSERELLE_CLE    clé SSH privée de la plateforme (facultatif)

Tous les chemins et clés viennent de l'environnement, jamais de Git.
"""

import os
import re
import secrets
import ssl
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import httpx

from commun.modeles import EntreeInventaire, Manifeste, canonique
from plateforme.signature import ed25519

__all__ = ["publier", "revoquer", "lire_inventaire", "PublicationRefusee"]


class PublicationRefusee(RuntimeError):
    """La passerelle a refusé le manifeste (signature, hash, âge, nonce)."""


def _signe() -> bool:
    return bool(os.environ.get("SAS_PASSERELLE_URL"))


def _client() -> httpx.Client:
    ctx = ssl.create_default_context(cafile=os.environ["SAS_TLS_CA"])
    ctx.load_cert_chain(os.environ["SAS_TLS_CERT"], os.environ["SAS_TLS_CLE"])
    return httpx.Client(base_url=os.environ["SAS_PASSERELLE_URL"], verify=ctx, timeout=120)


def _envoyer(chemin: str, m: Manifeste, fichiers: list[Path] = ()) -> None:
    cle = ed25519.charger_cle(Path(os.environ["SAS_CLE_SIGNATURE"]))
    data = {"manifeste": canonique(m).decode(), "signature": ed25519.signer(m, cle)}
    ouverts = [open(a, "rb") for a in fichiers]
    try:
        with _client() as c:
            r = c.post(chemin, data=data,
                       files=[("archives", (Path(a).name, f)) for a, f in zip(fichiers, ouverts)])
    finally:
        for f in ouverts:
            f.close()
    if r.status_code >= 300:
        raise PublicationRefusee(f"passerelle {r.status_code} : {r.text[:200]}")

_NOM_SUR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _config() -> tuple[str, str, list[str]]:
    hote = os.environ["SAS_PASSERELLE_SSH"]
    depot = os.environ.get("SAS_PASSERELLE_DEPOT", "/srv/pypi/packages").rstrip("/")
    cle = os.environ.get("SAS_PASSERELLE_CLE")
    options = ["-o", "BatchMode=yes"] + (["-i", cle] if cle else [])
    return hote, depot, options


def _verifier_pypi(ecosysteme) -> None:
    if str(ecosysteme) != "pypi":
        raise NotImplementedError("M0 : pip seulement")


def publier(ecosysteme, nom: str, version: str, archives: list[Path], verdict_id: int) -> None:
    _verifier_pypi(ecosysteme)
    if not archives:
        raise ValueError("aucune archive à publier")
    for a in archives:
        if not Path(a).is_file():
            raise FileNotFoundError(a)
    if _signe():
        _envoyer("/v1/publish", ed25519.manifeste_publication(
            ecosysteme, nom, version, list(map(Path, archives)), verdict_id), archives)
        return
    hote, depot, options = _config()
    subprocess.run(
        ["scp", *options, *map(str, archives), f"{hote}:{depot}/"], check=True, timeout=120
    )


def revoquer(ecosysteme, nom: str, version: str, raison: str) -> None:
    _verifier_pypi(ecosysteme)
    if not (_NOM_SUR.match(nom) and _NOM_SUR.match(version)) or ".." in nom + version:
        raise ValueError(f"nom ou version refusé : {nom!r} {version!r}")
    if _signe():
        _envoyer("/v1/revoke", Manifeste(
            type="revocation", ecosysteme=ecosysteme, nom=nom, version=version, raison=raison,
            emis_le=datetime.now(timezone.utc), nonce=secrets.token_hex(16)))
        return
    hote, depot, options = _config()
    # Les wheels remplacent « - » par « _ » dans le nom ; les sdist gardent souvent le nom tel quel.
    noms = dict.fromkeys([nom, nom.replace("-", "_")])
    motifs = " ".join(f"{depot}/{n}-{version}[.-]*" for n in noms)
    subprocess.run(["ssh", *options, hote, f"rm -f -- {motifs}"], check=True, timeout=60)


def lire_inventaire() -> list[EntreeInventaire]:
    if not _signe():
        return []
    with _client() as c:
        r = c.get("/v1/inventory")
    r.raise_for_status()
    return [EntreeInventaire.model_validate(e) for e in r.json()]
