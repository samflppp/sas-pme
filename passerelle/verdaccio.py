"""Dépôt npm de la passerelle : Verdaccio sans source amont (docs/architecture.md § 1).

Le récepteur y publie les seules versions npm dont la publication signée est vérifiée, et en retire
les versions révoquées, par l'API npm de Verdaccio (celle de `npm publish` et `npm unpublish`).
Verdaccio n'a aucun `uplink` : un serveur ne trouve que ce qui a été publié ici.

Seul le compte de publication du récepteur peut écrire (`publish` et `unpublish` dans la
configuration de Verdaccio) ; son jeton vient de l'environnement, jamais de Git.
"""
import base64
import hashlib
import io
import json
import tarfile
from urllib.parse import quote

import httpx


class ErreurDepot(RuntimeError):
    """Verdaccio a refusé l'opération, ou l'archive n'est pas un paquet npm lisible."""


def _cle(version: str) -> tuple:
    from plateforme.pipeline import semver     # même règle de tri que le pipeline
    return semver.cle(version) if semver.lire(version) else (-1,)


def package_json(tgz: bytes) -> dict:
    """Le package.json d'une archive npm, lu en mémoire (jamais extrait ni exécuté)."""
    try:
        with tarfile.open(fileobj=io.BytesIO(tgz), mode="r:gz") as t:
            for m in t:
                parties = m.name.split("/")
                if m.isreg() and len(parties) == 2 and parties[1] == "package.json":
                    return json.loads(t.extractfile(m).read())
    except (tarfile.TarError, ValueError, OSError) as e:
        raise ErreurDepot(f"archive npm illisible : {e}") from e
    raise ErreurDepot("archive npm sans package.json")


class Verdaccio:
    def __init__(self, url: str, jeton: str, client: httpx.Client | None = None):
        self.url = url.rstrip("/")
        self.client = client or httpx.Client(timeout=60)
        self.entetes = {"authorization": f"Bearer {jeton}"}

    def _chemin(self, nom: str) -> str:
        return f"{self.url}/{quote(nom, safe='@')}"

    def _lire(self, nom: str) -> dict | None:
        r = self.client.get(f"{self._chemin(nom)}?write=true", headers=self.entetes)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def publier(self, nom: str, version: str, fichier: str, tgz: bytes) -> None:
        """Publie une version ; déjà là avec la même archive : rien à faire (idempotent)."""
        pj = package_json(tgz)
        if pj.get("name") != nom or pj.get("version") != version:
            raise ErreurDepot(f"l'archive annonce {pj.get('name')} {pj.get('version')}, "
                              f"le manifeste {nom} {version}")
        shasum = hashlib.sha1(tgz).hexdigest()
        integrite = "sha512-" + base64.b64encode(hashlib.sha512(tgz).digest()).decode()
        dist = {"tarball": f"{self._chemin(nom)}/-/{fichier}", "shasum": shasum,
                "integrity": integrite}
        corps = {"_id": nom, "name": nom, "dist-tags": {"latest": version},
                 "versions": {version: {**pj, "_id": f"{nom}@{version}", "dist": dist}},
                 "_attachments": {fichier: {"content_type": "application/octet-stream",
                                            "data": base64.b64encode(tgz).decode(),
                                            "length": len(tgz)}}}
        r = self.client.put(self._chemin(nom), json=corps, headers=self.entetes)
        if r.status_code == 409:
            deja = ((self._lire(nom) or {}).get("versions") or {}).get(version) or {}
            if (deja.get("dist") or {}).get("shasum") == shasum:
                return
            raise ErreurDepot(f"{nom} {version} est déjà publiée avec une autre archive")
        if r.status_code >= 300:
            raise ErreurDepot(f"verdaccio {r.status_code} : {r.text[:200]}")
        self._latest(nom)

    def _latest(self, nom: str) -> None:
        """« latest » désigne la plus haute version présente : le serveur reçoit la dernière
        version vérifiée, même si une plus ancienne a été publiée après."""
        doc = self._lire(nom)
        if not doc or not doc.get("versions"):
            return
        haute = max(doc["versions"], key=_cle)
        if (doc.get("dist-tags") or {}).get("latest") != haute:
            r = self.client.put(f"{self.url}/-/package/{quote(nom, safe='@')}/dist-tags/latest",
                                json=haute, headers=self.entetes)
            if r.status_code >= 300:
                raise ErreurDepot(f"verdaccio {r.status_code} : {r.text[:200]}")

    def retirer(self, nom: str, version: str) -> list[str]:
        """Retire une version (et son archive) ; renvoie les archives retirées, [] si absente."""
        doc = self._lire(nom)
        if not doc or version not in (doc.get("versions") or {}):
            return []
        fichier = doc["versions"][version]["dist"]["tarball"].rsplit("/", 1)[-1]
        restantes = {v: x for v, x in doc["versions"].items() if v != version}
        if not restantes:                                  # dernière version : tout le paquet
            r = self.client.delete(f"{self._chemin(nom)}/-rev/{doc.get('_rev', '0')}",
                                   headers=self.entetes)
            if r.status_code >= 300:
                raise ErreurDepot(f"verdaccio {r.status_code} : {r.text[:200]}")
            return [fichier]
        doc["versions"] = restantes
        doc["time"] = {k: v for k, v in (doc.get("time") or {}).items() if k != version}
        doc["dist-tags"] = {t: v for t, v in (doc.get("dist-tags") or {}).items()
                            if v != version} or {}
        doc["dist-tags"]["latest"] = max(restantes, key=_cle)
        r = self.client.put(f"{self._chemin(nom)}/-rev/{doc.get('_rev', '0')}", json=doc,
                            headers=self.entetes)
        if r.status_code >= 300:
            raise ErreurDepot(f"verdaccio {r.status_code} : {r.text[:200]}")
        rev = (self._lire(nom) or {}).get("_rev", "0")
        r = self.client.delete(f"{self._chemin(nom)}/-/{fichier}/-rev/{rev}", headers=self.entetes)
        if r.status_code >= 300 and r.status_code != 404:
            raise ErreurDepot(f"verdaccio {r.status_code} : {r.text[:200]}")
        return [fichier]

    def versions(self, nom: str) -> list[str]:
        doc = self._lire(nom)
        return sorted((doc or {}).get("versions") or {}, key=_cle)
