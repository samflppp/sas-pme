"""Signature et publication vers la passerelle (C), docs/contrats.md § 4.

M1 (si SAS_PASSERELLE_URL est posée) : manifeste signé Ed25519, POST au récepteur en TLS mutuel.
  SAS_PASSERELLE_URL    ex. https://10.42.2.10:8443
  SAS_CLE_SIGNATURE     clé privée Ed25519 de la plateforme (PEM, 0600)
  SAS_TLS_CA            autorité qui a signé le certificat de la passerelle
  SAS_TLS_CERT, SAS_TLS_CLE   certificat client de la plateforme et sa clé

Stub M0, **refusé par défaut** (B, C3 : rien n'est publié sans signature). Il ne sert qu'aux tests
et se demande explicitement : SAS_PUBLICATION_NON_SIGNEE=oui-tests. Sans signature et sans cette
variable, publier() et revoquer() lèvent PublicationRefusee. Sinon, copie scp sans signature :
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

__all__ = ["publier", "revoquer", "lire_inventaire", "demander_installation", "lire_acces",
           "PublicationRefusee"]


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


def _stub_autorise() -> None:
    """Sans SAS_PASSERELLE_URL, refuser plutôt que publier en clair (B, C3)."""
    if os.environ.get("SAS_PUBLICATION_NON_SIGNEE") != "oui-tests":
        raise PublicationRefusee(
            "publication sans signature refusée : poser SAS_PASSERELLE_URL (lien signé). "
            "Le stub scp ne sert qu'aux tests (SAS_PUBLICATION_NON_SIGNEE=oui-tests).")


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
    _stub_autorise()
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
    _stub_autorise()
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
    # La passerelle peut joindre des champs hors contrat (ex. `machines`) : on ne garde que ceux
    # d'EntreeInventaire, qui refuse les champs inconnus.
    champs = EntreeInventaire.model_fields
    return [EntreeInventaire.model_validate({k: v for k, v in e.items() if k in champs})
            for e in r.json()]


# --- démo : installation demandée au serveur, journal d'accès (A pour C, conception-demo § 1) ---
def demander_installation(ecosysteme, nom: str, demande: int) -> int:
    """Demande au serveur de démo d'installer `nom` (la passerelle sert la dernière version
    vérifiée). Signée Ed25519, préfixe à part (passerelle.installation) ; rend son rang au guichet."""
    from passerelle import installation

    _verifier_pypi(ecosysteme)
    if not _signe():
        raise RuntimeError("passerelle non configurée (SAS_PASSERELLE_URL)")
    d = installation.DemandeInstallation(nom=nom, demande=demande, emis_le=datetime.now(timezone.utc),
                                         nonce=secrets.token_hex(16))
    texte, sig = installation.signer(d, ed25519.charger_cle(Path(os.environ["SAS_CLE_SIGNATURE"])))
    with _client() as c:
        r = c.post("/v1/install", data={"demande": texte, "signature": sig})
    if r.status_code >= 300:
        raise PublicationRefusee(f"passerelle {r.status_code} : {r.text[:200]}")
    return int(r.json()["n"])


def lire_acces(apres: int = 0) -> dict:
    """Les requêtes des serveurs à pypiserver après la ligne `apres` : {"total", "lignes"}."""
    if not _signe():
        raise RuntimeError("passerelle non configurée (SAS_PASSERELLE_URL)")
    with _client() as c:
        r = c.get("/v1/access", params={"apres": apres})
    r.raise_for_status()
    return r.json()
