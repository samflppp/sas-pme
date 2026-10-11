"""Mesure (B) : taux de détection et de fausses alertes d'un ensemble de contrôles sur le corpus."""
import importlib.util
from pathlib import Path

from commun.modeles import Ecosysteme, Niveau, Signal, Source

RACINE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("mesurer", RACINE / "mesure" / "mesurer.py")
mesurer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mesurer)

CORPUS = {
    "malveillants": [{"ecosysteme": "pypi", "nom": f"mal{i}", "version": "1.0", "ref": f"MAL-{i}"}
                     for i in range(4)],
    "sains": [{"ecosysteme": "pypi", "nom": f"sain{i}", "version": "2.0"} for i in range(5)],
}


def detecteur(eco, nom, version):
    """Détecte mal0 et mal1 (FORT), alerte faiblement mal2 (MOYEN), fausse alerte sur sain0."""
    niveau = {"mal0": Niveau.FORT, "mal1": Niveau.BLOQUANT, "mal2": Niveau.MOYEN,
              "sain0": Niveau.FORT}.get(nom)
    return [] if niveau is None else [Signal(ecosysteme=eco, nom=nom, version=version,
                                             source=Source.STATIQUE, niveau=niveau, sorte="test")]


def test_compte_detections_et_fausses_alertes():
    r = mesurer.mesurer(CORPUS, detecteur)
    assert (r.detectes, r.malveillants, r.fausses_alertes, r.sains) == (2, 4, 1, 5)
    assert r.taux_detection == 0.5 and r.taux_fausses_alertes == 0.2
    assert r.manques == ["mal2 1.0", "mal3 1.0"]      # MOYEN ne suffit pas à arrêter une version
    assert r.alertes_a_tort == ["sain0 2.0"]


def test_le_detecteur_recoit_l_ecosysteme_type():
    vus = []
    mesurer.mesurer(CORPUS, lambda eco, nom, version: vus.append(eco) or [])
    assert set(vus) == {Ecosysteme.PYPI}


def test_tableau_markdown():
    md = mesurer.tableau({"Contrôles seuls": mesurer.mesurer(CORPUS, detecteur)})
    assert "| Contrôles seuls | 2 / 4 (50 %) | 1 / 5 (20 %) |" in md


def test_le_rapport_dit_ses_limites():
    md = mesurer.rapport(CORPUS, {"Contrôles seuls": mesurer.mesurer(CORPUS, detecteur)})
    assert "## Limites" in md and "OpenSSF" in md


def test_une_version_non_mesurable_sort_du_compte_et_est_listee():
    def detecteur_partiel(eco, nom, version):
        return None if nom in ("mal3", "sain4") else detecteur(eco, nom, version)
    r = mesurer.mesurer(CORPUS, detecteur_partiel)
    assert (r.detectes, r.malveillants, r.fausses_alertes, r.sains) == (2, 3, 1, 4)
    assert r.non_mesures == ["mal3 1.0", "sain4 2.0"]
    md = mesurer.rapport(CORPUS, {"Statique": r})
    assert "Non mesurées (2)" in md and "`sain4 2.0`" in md


# --- M3 : trois colonnes (contrôles seuls ; + sandbox ; + LLM/RAG) --------------------------------
from commun.modeles import RapportSandbox  # noqa: E402

VIDE = RapportSandbox(requetes_dns=[], connexions=[], fichiers_sensibles=[], leurres_lus=[],
                      processus=[], code_sortie=0, duree_s=1.0, delai_depasse=False)


def test_la_colonne_sandbox_ajoute_les_signaux_du_rapport_et_note_les_analyses_impossibles():
    rapports = {"mal3": VIDE.model_copy(update={"leurres_lus": ["~/.aws/credentials"]}),
                "sain1": VIDE.model_copy(update={"requetes_dns": ["telemetrie.invalid"]})}

    def rapport(eco, nom, version):
        if nom == "sain2":
            raise RuntimeError("docker absent")
        return rapports.get(nom, VIDE)

    d = mesurer.avec_sandbox(detecteur, rapport)
    r = mesurer.mesurer(CORPUS, d)
    assert (r.detectes, r.fausses_alertes) == (3, 3)      # + mal3 ; + sain1 (DNS) et sain2
    assert d.impossibles == ["sain2 2.0"]                  # comme le pipeline : « à revoir »


def test_la_colonne_llm_n_interroge_le_llm_que_la_ou_il_peut_changer_le_resultat():
    appels = []

    def llm(eco, nom, version, signaux):
        appels.append(nom)
        return [Signal(ecosysteme=eco, nom=nom, version=version, source=Source.LLM,
                       niveau=Niveau.FORT, sorte="llm")]

    def avec_info(eco, nom, version):          # mal3 : un constat INFO seul ne suffit pas
        info = [Signal(ecosysteme=eco, nom=nom, version=version, source=Source.STATIQUE,
                       niveau=Niveau.INFO, sorte="domaine")] if nom == "mal3" else []
        return detecteur(eco, nom, version) + info

    d = mesurer.avec_llm(avec_info, llm)
    r = mesurer.mesurer(CORPUS, d)
    # mal0, mal1, sain0 : déjà arrêtées. Sans constat MOYEN hors LLM (mal3 n'a qu'un INFO), un FORT
    # du LLM redescend (plateforme.pipeline.llm) : inutile de l'interroger. Reste mal2 (MOYEN).
    assert appels == ["mal2"] and d.appels == 1
    assert (r.detectes, r.fausses_alertes) == (3, 1)


def test_le_tableau_final_a_les_trois_lignes_dans_l_ordre():
    r = mesurer.mesurer(CORPUS, detecteur)
    t = mesurer.tableau({"Contrôles seuls": r, "+ sandbox": r, "+ LLM/RAG": r})
    assert [l.split("|")[1].strip() for l in t.splitlines()[2:]] == [
        "Contrôles seuls", "+ sandbox", "+ LLM/RAG"]
