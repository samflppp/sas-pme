"""Boucle de traitement (B, point H3) : en_attente mûre → analyse → verdict → publication."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from commun.modeles import Ecosysteme, Etat, RapportSandbox, Version
from plateforme.db.acces import Base
from plateforme.pipeline import traitement

MAINTENANT = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
VIDE = RapportSandbox(requetes_dns=[], connexions=[], fichiers_sensibles=[], leurres_lus=[],
                      processus=[], code_sortie=0, duree_s=0.0, delai_depasse=False)


def version(nom: str, age_j: int) -> Version:
    return Version(ecosysteme=Ecosysteme.PYPI, nom=nom, version="1.0",
                   publiee_le=MAINTENANT - timedelta(days=age_j), detectee_le=MAINTENANT,
                   etat=Etat.EN_ATTENTE)


@pytest.fixture
def base(tmp_path):
    b = Base(str(tmp_path / "sas.db"))
    b.enregistrer_version(version("mure", 5))
    b.enregistrer_version(version("jeune", 1))
    return b


@pytest.fixture
def faux(tmp_path):
    """Faux de PyPI (B), de la sandbox et de la signature (C), qui notent leurs appels."""
    appels = {"executer": [], "publier": []}

    def telecharger(nom, version, dossier):
        if nom == "casse":
            raise ValueError("sha256 différent")
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / f"{nom}-{version}.tar.gz").write_bytes(b"x")
        (dossier / f"{nom}-{version}-py3-none-any.whl").write_bytes(b"x")
        return sorted(dossier.iterdir())

    def executer(eco, archive, module, duree_max_s=120):
        appels["executer"].append((archive.name, module))
        return VIDE

    def publier(eco, nom, version, archives, verdict_id):
        appels["publier"].append((nom, version, [a.name for a in archives], verdict_id))

    return dict(dossier=tmp_path / "archives", telecharger=telecharger, executer=executer,
                publier=publier), appels


def etat(base, nom):
    return base.lire_version(Ecosysteme.PYPI, nom, "1.0").etat


def test_une_version_mure_est_analysee_approuvee_et_publiee(base, faux):
    deps, appels = faux
    resultats = traitement.traiter(base, MAINTENANT, **deps)
    assert [(v.nom, e) for v, e in resultats] == [("mure", Etat.PUBLIEE)]
    assert etat(base, "mure") is Etat.PUBLIEE
    assert etat(base, "jeune") is Etat.EN_ATTENTE         # délai pas écoulé : on n'y touche pas
    assert appels["executer"] == [("mure-1.0-py3-none-any.whl", "mure")]
    fiche = base.fiche(Ecosysteme.PYPI, "mure", "1.0")
    assert fiche.rapport_sandbox == VIDE and fiche.verdict.etat is Etat.APPROUVEE
    assert appels["publier"] == [("mure", "1.0", ["mure-1.0-py3-none-any.whl", "mure-1.0.tar.gz"],
                                  fiche.verdict_id)]
    assert base.verifier_journal() == (True, None)


def test_un_echec_d_analyse_met_a_revoir_sans_publier_et_continue(base, faux):
    deps, appels = faux
    base.enregistrer_version(version("casse", 10))
    resultats = dict((v.nom, e) for v, e in traitement.traiter(base, MAINTENANT, **deps))
    assert resultats == {"casse": Etat.A_REVOIR, "mure": Etat.PUBLIEE}
    assert "sha256" in base.fiche(Ecosysteme.PYPI, "casse", "1.0").raison
    assert [p[0] for p in appels["publier"]] == ["mure"]


def test_un_echec_de_publication_laisse_approuvee_mais_pas_publiee(base, faux):
    deps, _ = faux
    def publier_en_panne(*_a, **_k):
        raise ConnectionError("passerelle injoignable")
    deps["publier"] = publier_en_panne
    assert [e for _, e in traitement.traiter(base, MAINTENANT, **deps)] == [Etat.APPROUVEE]
    assert etat(base, "mure") is Etat.APPROUVEE


def test_sans_la_sandbox_de_c_rien_n_est_approuve(base, faux, monkeypatch):
    deps, _ = faux
    del deps["executer"]
    monkeypatch.setitem(sys.modules, "plateforme.sandbox", None)  # module de C absent
    with pytest.raises(RuntimeError, match="sandbox"):
        traitement.traiter(base, MAINTENANT, **deps)
    assert etat(base, "mure") is Etat.EN_ATTENTE
