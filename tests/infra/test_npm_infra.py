"""Infra npm (C) : Verdaccio sans source amont, publication au seul récepteur, script hors ligne."""
import re
import subprocess
from pathlib import Path

import yaml

INFRA = Path(__file__).resolve().parents[2] / "infra"
CONFIG = yaml.safe_load((INFRA / "passerelle" / "verdaccio.yaml").read_text())


def _service(nom: str) -> str:
    return (INFRA / "passerelle" / nom).read_text()


def test_verdaccio_n_a_aucune_source_amont_et_seul_le_recepteur_ecrit():
    assert CONFIG["uplinks"] == {}
    for regle in CONFIG["packages"].values():
        assert "proxy" not in regle                        # aucun repli vers npmjs
        assert regle["publish"] == regle["unpublish"] == "recepteur"
    assert CONFIG["auth"]["htpasswd"]["max_users"] == -1   # plus d'inscription
    assert CONFIG["web"]["enable"] is False


def test_le_journal_de_verdaccio_est_celui_que_lit_le_recepteur():
    assert CONFIG["log"] == {"type": "file", "path": "/var/lib/sas/verdaccio.log",
                             "format": "json", "level": "http"}
    recepteur = _service("recepteur.service")
    assert "Environment=SAS_JOURNAL_NPM=/var/lib/sas/verdaccio.log" in recepteur
    assert "Environment=SAS_VERDACCIO_JETON=/var/lib/sas-recepteur/verdaccio.jeton" in recepteur


def test_le_service_verdaccio_est_verrouille():
    s = _service("verdaccio.service")
    for ligne in ("User=verdaccio", "NoNewPrivileges=yes", "ProtectSystem=strict",
                  "ProtectHome=yes", "PrivateTmp=yes"):
        assert ligne in s, ligne


def test_le_script_npm_est_valide_verifie_node_et_n_utilise_pas_la_cle_de_la_plateforme():
    script = INFRA / "aws" / "installer_npm.sh"
    subprocess.run(["bash", "-n", str(script)], check=True)
    texte = script.read_text()
    assert "sha256sum -c" in texte                         # Node vérifié avant usage
    assert "--ignore-scripts" in texte                     # Verdaccio installé sans ses scripts
    assert "sas_passerelle" not in texte                   # la clé retirée par installer.sh (C3)
    assert re.search(r"registry=http://passerelle:4873/", texte)


def test_le_recepteur_recoit_httpx_pour_parler_a_verdaccio():
    texte = (INFRA / "aws" / "installer.sh").read_text()
    assert texte.count("httpx") >= 2                       # téléchargé, puis installé
