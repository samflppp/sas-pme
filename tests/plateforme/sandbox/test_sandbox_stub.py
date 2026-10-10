"""Stub M0 de la sandbox (contrats.md § 3) : renvoie un rapport vide."""

import pytest

from plateforme.sandbox import Ecosysteme, RapportSandbox, executer


def test_executer_renvoie_un_rapport_vide(tmp_path):
    archive = tmp_path / "requests-2.32.4-py3-none-any.whl"
    archive.write_bytes(b"faux")

    rapport = executer(Ecosysteme.PYPI, archive, "requests")

    assert isinstance(rapport, RapportSandbox)
    assert rapport.requetes_dns == []
    assert rapport.connexions == []
    assert rapport.fichiers_sensibles == []
    assert rapport.leurres_lus == []
    assert rapport.processus == []
    assert rapport.code_sortie == 0
    assert rapport.delai_depasse is False


def test_executer_refuse_une_archive_absente(tmp_path):
    with pytest.raises(FileNotFoundError):
        executer(Ecosysteme.PYPI, tmp_path / "absente.whl", "absente")
