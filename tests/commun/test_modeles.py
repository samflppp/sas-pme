from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from commun.modeles import (
    Ecosysteme, EntreeInventaire, Etat, FichierManifeste, Manifeste, Niveau,
    RapportSandbox, Signal, Source, Verdict, Version, canonique,
)

MAINTENANT = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)


def signal(**surcharges) -> Signal:
    base = dict(ecosysteme=Ecosysteme.PYPI, nom="demo", version="1.1",
                source=Source.STATIQUE, niveau=Niveau.FORT, sorte="typosquat", preuve={})
    base.update(surcharges)
    return Signal(**base)


def test_enums_se_relisent_depuis_leur_texte():
    assert Etat("publiee") is Etat.PUBLIEE
    assert Niveau("bloquant") is Niveau.BLOQUANT
    assert Ecosysteme("npm") is Ecosysteme.NPM


def test_niveaux_ordonnes_par_gravite():
    assert Niveau.INFO.rang < Niveau.MOYEN.rang < Niveau.FORT.rang < Niveau.BLOQUANT.rang


def test_un_signal_llm_ne_peut_pas_etre_bloquant():
    signal(source=Source.LLM, niveau=Niveau.FORT)
    with pytest.raises(ValidationError):
        signal(source=Source.LLM, niveau=Niveau.BLOQUANT)


def test_un_article_de_source_libre_ne_peut_pas_etre_bloquant():
    signal(source=Source.VEILLE, niveau=Niveau.BLOQUANT, structure=True)
    with pytest.raises(ValidationError):
        signal(source=Source.VEILLE, niveau=Niveau.BLOQUANT, structure=False)


def test_un_verdict_ne_peut_conclure_que_approuvee_a_revoir_ou_bloquee():
    Verdict(etat=Etat.A_REVOIR, raison="un signal fort", signaux=[signal()])
    with pytest.raises(ValidationError):
        Verdict(etat=Etat.PUBLIEE, raison="non", signaux=[])


def test_version_et_rapport_et_inventaire_se_construisent():
    Version(ecosysteme=Ecosysteme.PYPI, nom="requests", version="2.32.4",
            publiee_le=MAINTENANT, detectee_le=MAINTENANT, etat=Etat.EN_ATTENTE)
    RapportSandbox(requetes_dns=["exfil.demo.invalid"], connexions=["exfil.demo.invalid:443"],
                   fichiers_sensibles=["/root/.aws/credentials"], leurres_lus=["AWS_SECRET_ACCESS_KEY"],
                   processus=["python"], code_sortie=0, duree_s=61.2, delai_depasse=False)
    EntreeInventaire(ecosysteme=Ecosysteme.NPM, nom="left-pad", version="1.3.0",
                     telechargements=4, dernier=MAINTENANT)


def test_le_manifeste_canonique_est_stable_et_sans_espaces():
    m = Manifeste(type="publication", ecosysteme=Ecosysteme.PYPI, nom="requests", version="2.32.4",
                  fichiers=[FichierManifeste(nom="requests-2.32.4-py3-none-any.whl", sha256="ab" * 32)],
                  verdict_id=42, approuve_le=MAINTENANT, emis_le=MAINTENANT, nonce="8f1c")
    octets = canonique(m)
    assert octets == canonique(Manifeste.model_validate_json(octets))
    texte = octets.decode()
    assert " " not in texte
    assert texte.index('"approuve_le"') < texte.index('"ecosysteme"') < texte.index('"version"')


def test_un_sha256_mal_forme_est_refuse():
    with pytest.raises(ValidationError):
        FichierManifeste(nom="x.whl", sha256="pas-un-hash")
