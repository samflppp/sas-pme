"""Signature Ed25519 des manifestes, côté plateforme (docs/contrats.md § 4)."""

import base64
from datetime import datetime, timezone

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from commun.modeles import Ecosysteme, FichierManifeste, Manifeste, canonique
from plateforme.signature import ed25519


def _manifeste(**k) -> Manifeste:
    champs = dict(type="publication", ecosysteme=Ecosysteme.PYPI, nom="requests", version="2.32.4",
                  fichiers=[FichierManifeste(nom="requests-2.32.4-py3-none-any.whl", sha256="a" * 64)],
                  verdict_id=42, emis_le=datetime(2026, 10, 11, 9, 0, 5, tzinfo=timezone.utc),
                  nonce="8f1c")
    champs.update(k)
    return Manifeste(**champs)


def test_generer_cree_une_cle_privee_lisible_par_moi_seul(tmp_path):
    chemin = tmp_path / "signature.pem"
    ed25519.generer_cle(chemin)
    assert chemin.read_bytes().startswith(b"-----BEGIN PRIVATE KEY-----")
    assert chemin.stat().st_mode & 0o077 == 0


def test_generer_refuse_d_ecraser_une_cle(tmp_path):
    chemin = tmp_path / "signature.pem"
    ed25519.generer_cle(chemin)
    with pytest.raises(FileExistsError):
        ed25519.generer_cle(chemin)


def test_la_signature_se_verifie_avec_la_cle_publique(tmp_path):
    cle = ed25519.generer_cle(tmp_path / "signature.pem")
    m = _manifeste()
    signature = base64.b64decode(ed25519.signer(m, cle))
    publique = load_pem_public_key(ed25519.cle_publique_pem(cle))
    publique.verify(signature, canonique(m))          # ne lève rien


def test_un_manifeste_modifie_ne_se_verifie_plus(tmp_path):
    cle = ed25519.generer_cle(tmp_path / "signature.pem")
    signature = base64.b64decode(ed25519.signer(_manifeste(), cle))
    publique = load_pem_public_key(ed25519.cle_publique_pem(cle))
    with pytest.raises(InvalidSignature):
        publique.verify(signature, canonique(_manifeste(version="2.32.5")))


def test_charger_relit_la_meme_cle(tmp_path):
    chemin = tmp_path / "signature.pem"
    cle = ed25519.generer_cle(chemin)
    assert ed25519.cle_publique_pem(ed25519.charger_cle(chemin)) == ed25519.cle_publique_pem(cle)


def test_nouveau_manifeste_hashe_les_archives_et_tire_un_nonce(tmp_path):
    archive = tmp_path / "requests-2.32.4-py3-none-any.whl"
    archive.write_bytes(b"contenu")
    m1 = ed25519.manifeste_publication(Ecosysteme.PYPI, "requests", "2.32.4", [archive], 42)
    m2 = ed25519.manifeste_publication(Ecosysteme.PYPI, "requests", "2.32.4", [archive], 42)
    assert m1.fichiers == [FichierManifeste(
        nom=archive.name,
        sha256="3016ef88e3166466281c563b984abed5412a2de823d37ed99c2af39be422fab1")]
    assert m1.type == "publication" and m1.verdict_id == 42
    assert len(m1.nonce) >= 32 and m1.nonce != m2.nonce
    assert m1.emis_le.tzinfo is not None
