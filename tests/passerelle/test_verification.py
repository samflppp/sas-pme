"""Vérification d'une publication par la passerelle (docs/contrats.md § 4, règles de la passerelle)."""

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from commun.modeles import Ecosysteme, FichierManifeste, Manifeste, canonique
from passerelle import verification as v
from plateforme.signature import ed25519

MAINTENANT = datetime(2026, 10, 11, 9, 5, tzinfo=timezone.utc)
CONTENU = b"une roue"


@pytest.fixture
def cles(tmp_path):
    privee = ed25519.generer_cle(tmp_path / "plateforme.pem")
    autre = ed25519.generer_cle(tmp_path / "usurpateur.pem")
    return privee, ed25519.cle_publique_pem(privee), autre


def _manifeste(**k) -> Manifeste:
    champs = dict(type="publication", ecosysteme=Ecosysteme.PYPI, nom="requests", version="2.32.4",
                  fichiers=[FichierManifeste(nom="requests-2.32.4-py3-none-any.whl",
                                             sha256=hashlib.sha256(CONTENU).hexdigest())],
                  verdict_id=42, emis_le=MAINTENANT - timedelta(minutes=1), nonce="n" * 32)
    champs.update(k)
    return Manifeste(**champs)


def _verifier(cles, m, signee_par=None, archives=None, nonces=None):
    privee, publique, _ = cles
    return v.verifier(canonique(m), ed25519.signer(m, signee_par or privee),
                      {"requests-2.32.4-py3-none-any.whl": CONTENU} if archives is None else archives,
                      publique, MAINTENANT, set() if nonces is None else nonces)


def test_une_publication_bien_signee_est_acceptee(cles):
    m = _manifeste()
    assert _verifier(cles, m) == m


def test_une_publication_signee_par_une_autre_cle_est_refusee(cles):
    with pytest.raises(v.SignatureInvalide):
        _verifier(cles, _manifeste(), signee_par=cles[2])


def test_un_manifeste_retouche_apres_signature_est_refuse(cles):
    privee, publique, _ = cles
    signature = ed25519.signer(_manifeste(), privee)
    retouche = canonique(_manifeste(version="6.6.6"))
    with pytest.raises(v.SignatureInvalide):
        v.verifier(retouche, signature, {"requests-2.32.4-py3-none-any.whl": CONTENU},
                   publique, MAINTENANT, set())


def test_une_signature_illisible_est_refusee(cles):
    _, publique, _ = cles
    with pytest.raises(v.SignatureInvalide):
        v.verifier(canonique(_manifeste()), "pas du base64 !", {}, publique, MAINTENANT, set())


def test_une_archive_dont_le_hash_differe_est_refusee(cles):
    with pytest.raises(v.HashDifferent):
        _verifier(cles, _manifeste(), archives={"requests-2.32.4-py3-none-any.whl": b"piegee"})


def test_une_archive_en_plus_ou_en_moins_est_refusee(cles):
    with pytest.raises(v.HashDifferent):
        _verifier(cles, _manifeste(), archives={})
    with pytest.raises(v.HashDifferent):
        _verifier(cles, _manifeste(), archives={"requests-2.32.4-py3-none-any.whl": CONTENU,
                                                 "intrus.whl": b"x"})


def test_un_manifeste_de_plus_de_10_minutes_est_refuse(cles):
    with pytest.raises(v.ManifestePerime):
        _verifier(cles, _manifeste(emis_le=MAINTENANT - timedelta(minutes=11)))


def test_un_manifeste_venu_du_futur_est_refuse(cles):
    with pytest.raises(v.ManifestePerime):
        _verifier(cles, _manifeste(emis_le=MAINTENANT + timedelta(minutes=11)))


def test_un_nonce_deja_vu_est_refuse_et_un_nouveau_est_retenu(cles):
    nonces: set[str] = set()
    _verifier(cles, _manifeste(), nonces=nonces)
    assert "n" * 32 in nonces
    with pytest.raises(v.NonceDejaVu):
        _verifier(cles, _manifeste(), nonces=nonces)


def test_un_refus_ne_consomme_pas_le_nonce(cles):
    nonces: set[str] = set()
    with pytest.raises(v.HashDifferent):
        _verifier(cles, _manifeste(), archives={}, nonces=nonces)
    assert nonces == set()


def test_un_nom_de_fichier_avec_un_chemin_est_refuse(cles):
    m = _manifeste(fichiers=[FichierManifeste(nom="../../etc/cron.d/x",
                                              sha256=hashlib.sha256(CONTENU).hexdigest())])
    with pytest.raises(v.HashDifferent):
        _verifier(cles, m, archives={"../../etc/cron.d/x": CONTENU})


def test_les_codes_http_suivent_le_contrat():
    assert (v.HashDifferent.code, v.SignatureInvalide.code, v.NonceDejaVu.code) == (400, 401, 409)
