"""Stub M0 de la signature (contrats.md § 4) : copie des archives par scp, sans signer."""

import subprocess

import pytest

from plateforme import signature


@pytest.fixture
def commandes(monkeypatch):
    """Remplace subprocess.run : enregistre les commandes au lieu de les lancer."""
    lancees = []

    def faux_run(cmd, **kwargs):
        lancees.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(signature.subprocess, "run", faux_run)
    monkeypatch.setenv("SAS_PASSERELLE_SSH", "ubuntu@10.42.2.10")
    monkeypatch.setenv("SAS_PASSERELLE_DEPOT", "/srv/pypi/packages")
    monkeypatch.delenv("SAS_PASSERELLE_CLE", raising=False)
    return lancees


def test_publier_copie_les_archives_par_scp(tmp_path, commandes):
    whl = tmp_path / "requests-2.32.4-py3-none-any.whl"
    whl.write_bytes(b"faux")

    signature.publier("pypi", "requests", "2.32.4", [whl], verdict_id=1)

    assert len(commandes) == 1
    cmd = commandes[0]
    assert cmd[0] == "scp"
    assert str(whl) in cmd
    assert cmd[-1] == "ubuntu@10.42.2.10:/srv/pypi/packages/"


def test_publier_utilise_la_cle_si_fournie(tmp_path, commandes, monkeypatch):
    monkeypatch.setenv("SAS_PASSERELLE_CLE", "/home/ubuntu/.ssh/sas_passerelle")
    whl = tmp_path / "requests-2.32.4-py3-none-any.whl"
    whl.write_bytes(b"faux")

    signature.publier("pypi", "requests", "2.32.4", [whl], verdict_id=1)

    cmd = commandes[0]
    assert cmd[cmd.index("-i") + 1] == "/home/ubuntu/.ssh/sas_passerelle"


def test_publier_refuse_une_liste_vide(commandes):
    with pytest.raises(ValueError):
        signature.publier("pypi", "requests", "2.32.4", [], verdict_id=1)
    assert commandes == []


def test_publier_refuse_une_archive_absente(tmp_path, commandes):
    with pytest.raises(FileNotFoundError):
        signature.publier("pypi", "requests", "2.32.4", [tmp_path / "x.whl"], verdict_id=1)
    assert commandes == []


def test_publier_refuse_npm_en_m0(tmp_path, commandes):
    tgz = tmp_path / "left-pad-1.3.0.tgz"
    tgz.write_bytes(b"faux")
    with pytest.raises(NotImplementedError):
        signature.publier("npm", "left-pad", "1.3.0", [tgz], verdict_id=1)


def test_publier_echoue_si_scp_echoue(tmp_path, monkeypatch, commandes):
    def run_en_echec(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(signature.subprocess, "run", run_en_echec)
    whl = tmp_path / "requests-2.32.4-py3-none-any.whl"
    whl.write_bytes(b"faux")
    with pytest.raises(subprocess.CalledProcessError):
        signature.publier("pypi", "requests", "2.32.4", [whl], verdict_id=1)


def test_revoquer_supprime_les_archives_de_la_version(commandes):
    signature.revoquer("pypi", "requests", "2.32.4", raison="test")

    cmd = commandes[0]
    assert cmd[0] == "ssh"
    assert "ubuntu@10.42.2.10" in cmd
    assert cmd[-1] == "rm -f -- /srv/pypi/packages/requests-2.32.4[.-]*"


@pytest.mark.parametrize("nom,version", [
    ("../etc", "1.0"), ("requests", "1.0;rm -rf /"), ("req uests", "1.0"), ("requests", ""),
])
def test_revoquer_refuse_un_nom_ou_une_version_douteux(commandes, nom, version):
    with pytest.raises(ValueError):
        signature.revoquer("pypi", nom, version, raison="test")
    assert commandes == []


def test_lire_inventaire_renvoie_une_liste_vide_en_m0():
    assert signature.lire_inventaire() == []
