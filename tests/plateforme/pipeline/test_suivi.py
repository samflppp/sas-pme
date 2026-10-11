"""Suivi en direct de la pipeline (A dans le dossier de B, conception-demo § 2) : une ligne par
étape, au journal et à un rappel ; l'explication du LLM lue en flux, mot à mot."""
import io
import json
import tarfile
import zipfile
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from commun.modeles import Ecosysteme, Etat, Niveau, RapportSandbox, Signal, Source, Version
from plateforme.db.acces import Base
from plateforme.pipeline import llm, suivi, traitement
from plateforme.pipeline.llm import ResultatLLM

MAINTENANT = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
VIDE = RapportSandbox(requetes_dns=[], connexions=[], fichiers_sensibles=[], leurres_lus=[],
                      processus=[], code_sortie=0, duree_s=0.0, delai_depasse=False)


def ecrire_archives(dossier, nom, version):
    dossier.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dossier / f"{nom}-{version}-py3-none-any.whl", "w") as z:
        z.writestr(f"{nom}/__init__.py", "X = 1\n")
    with tarfile.open(dossier / f"{nom}-{version}.tar.gz", "w:gz") as t:
        donnees = b"from setuptools import setup\nsetup()\n"
        info = tarfile.TarInfo(f"{nom}-{version}/setup.py")
        info.size = len(donnees)
        t.addfile(info, io.BytesIO(donnees))

SUJET = "pypi:mure@1.0"
ETAPES = ["telechargement", "sandbox", "statique", "ia", "politique", "publication"]


@pytest.fixture
def base(tmp_path):
    b = Base(str(tmp_path / "sas.db"))
    b.enregistrer_version(Version(ecosysteme=Ecosysteme.PYPI, nom="mure", version="1.0",
                                  publiee_le=MAINTENANT - timedelta(days=5),
                                  detectee_le=MAINTENANT, etat=Etat.EN_ATTENTE))
    return b


def deps(tmp_path, executer=None, llm_=None):
    def telecharger(nom, version, dossier):
        ecrire_archives(dossier, nom, version)
        return sorted(dossier.iterdir())
    return dict(dossier=tmp_path / "archives", telecharger=telecharger,
                executer=executer or (lambda eco, a, m, duree_max_s=120: VIDE),
                publier=lambda *a: None, veiller=lambda b, m: None,
                controler_meta=lambda v, p, m: [],
                llm=llm_ or (lambda b, v, s, r: ResultatLLM(explication="Rien à signaler.")))


def test_chaque_etape_commence_et_finit_dans_l_ordre(base, tmp_path):
    vus = []
    traitement.traiter(base, MAINTENANT, suivi=lambda *e: vus.append(e), **deps(tmp_path))
    assert {e[0] for e in vus} == {SUJET}
    bornes = [(etape, etat) for _, etape, etat, _ in vus if etat in ("debut", "fin")]
    assert bornes == [(x, y) for x in ETAPES for y in ("debut", "fin")]
    fin = {etape: detail for _, etape, etat, detail in vus if etat == "fin"}
    assert fin["telechargement"]["archives"] == ["mure-1.0-py3-none-any.whl", "mure-1.0.tar.gz"]
    assert fin["politique"]["verdict"] == "approuvee"
    assert fin["publication"]["resultat"] == "publiee"
    assert fin["ia"]["explication"] == "Rien à signaler."
    assert all(d["duree_s"] >= 0 for d in fin.values())


def test_les_etapes_finies_sont_au_journal_chaine(base, tmp_path):
    traitement.traiter(base, MAINTENANT, **deps(tmp_path))      # sans rappel : le journal suffit
    etapes = [e for e in base.journal() if e.action == "etape"]
    assert [e.charge["etape"] for e in etapes] == ETAPES
    assert all(e.sujet == SUJET and e.charge["etat"] == "fin" for e in etapes)
    assert base.verifier_journal() == (True, None)


def test_une_etape_en_erreur_est_dite_et_la_version_va_a_revoir(base, tmp_path):
    def executer(*a, **k):
        raise RuntimeError("docker absent")
    vus = []
    traitement.traiter(base, MAINTENANT, suivi=lambda *e: vus.append(e), **deps(tmp_path, executer))
    erreurs = [(etape, d["erreur"]) for _, etape, etat, d in vus if etat == "erreur"]
    assert erreurs == [("sandbox", "RuntimeError: docker absent")]
    assert base.lire_version(Ecosysteme.PYPI, "mure", "1.0").etat is Etat.A_REVOIR
    journal = [e.charge for e in base.journal() if e.action == "etape"]
    assert journal[-1]["etape"] == "sandbox" and journal[-1]["etat"] == "erreur"


def test_un_rappel_qui_plante_ne_change_rien_au_traitement(base, tmp_path):
    def rappel(*e):
        raise ValueError("onglet fermé")
    resultats = traitement.traiter(base, MAINTENANT, suivi=rappel, **deps(tmp_path))
    assert [e for _, e in resultats] == [Etat.PUBLIEE]


def test_le_llm_du_pipeline_ecrit_son_explication_au_fil_de_l_eau(base, tmp_path, monkeypatch):
    """Le vrai `_llm_reseau` reçoit de quoi écrire les morceaux : ils arrivent dans l'étape « ia »."""
    def faux_analyser(base, v, signaux, rapport, *, client, url, modele, passages=(), morceau=None):
        for bout in ("Le paquet ", "Le paquet est sain."):
            morceau(bout)
        return ResultatLLM(explication="Le paquet est sain.")
    monkeypatch.setattr(llm, "analyser", faux_analyser)
    monkeypatch.setattr(traitement.rag, "ouvrir", lambda: None)
    monkeypatch.setattr(traitement.rag, "passages", lambda *a: [])
    vus = []
    d = deps(tmp_path)
    del d["llm"]
    traitement.traiter(base, MAINTENANT, suivi=lambda *e: vus.append(e), **d)
    flux = [x["explication"] for _, etape, etat, x in vus if etat == "flux"]
    assert flux == ["Le paquet ", "Le paquet est sain."]
    assert [etape for _, etape, etat, _ in vus if etat == "flux"] == ["ia", "ia"]


# --- le LLM en flux ---------------------------------------------------------------------------
V = Version(ecosysteme=Ecosysteme.PYPI, nom="demo", version="1.0", publiee_le=MAINTENANT,
            detectee_le=MAINTENANT, etat=Etat.EN_ANALYSE)
CONSTAT = Signal(ecosysteme=Ecosysteme.PYPI, nom="demo", version="1.0", source=Source.STATIQUE,
                 niveau=Niveau.MOYEN, sorte="reseau", preuve={"extrait": "urlopen(x)"})
REPONSE = {"signaux": [], "explication": "Le paquet ouvre une connexion \"réseau\" : à vérifier.",
           "refs_rag": []}


def en_morceaux(texte: str, taille: int = 7) -> bytes:
    lignes = [json.dumps({"message": {"content": texte[i:i + taille]}, "done": False})
              for i in range(0, len(texte), taille)]
    lignes.append(json.dumps({"message": {"content": ""}, "done": True}))
    return ("\n".join(lignes) + "\n").encode()


@respx.mock
def test_en_flux_l_explication_grandit_et_le_resultat_est_le_meme(tmp_path):
    base = Base(str(tmp_path / "sas.db"))
    route = respx.post("http://ollama.test/api/chat").mock(
        return_value=httpx.Response(200, content=en_morceaux(json.dumps(REPONSE, ensure_ascii=False))))
    vus = []
    with httpx.Client() as client:
        r = llm.analyser(base, V, [CONSTAT], VIDE, client=client, url="http://ollama.test",
                         modele="m", morceau=vus.append)
    assert json.loads(route.calls.last.request.content)["stream"] is True
    assert r.explication == REPONSE["explication"]
    assert vus and vus[-1] == REPONSE["explication"]
    assert all(b.startswith(a) for a, b in zip(vus, vus[1:]))      # elle ne fait que grandir
    assert '\\"' not in "".join(vus)                                 # échappements JSON décodés


@respx.mock
def test_en_flux_une_reponse_hors_schema_reste_ignoree(tmp_path):
    base = Base(str(tmp_path / "sas.db"))
    base.enregistrer_version(V)
    hors = json.dumps({"signaux": [], "explication": "x", "refs_rag": [], "approuver": True})
    respx.post("http://ollama.test/api/chat").mock(
        return_value=httpx.Response(200, content=en_morceaux(hors)))
    with httpx.Client() as client:
        r = llm.analyser(base, V, [CONSTAT], VIDE, client=client, url="http://ollama.test",
                         modele="m", morceau=lambda t: None)
    assert r == ResultatLLM()
    assert [e.action for e in base.journal()][-1] == "llm_hors_schema"


@pytest.mark.parametrize("brut, attendu", [
    ('{"signaux": [], "explication": "Le pa', "Le pa"),
    ('{"signaux": [], "explication": "un \\"mot', 'un "mot'),
    ('{"signaux": [], "explication": "fin\\', "fin"),           # échappement coupé : attendu
    ('{"signaux": [], "explication": "a\\u00e9b"}', "aéb"),
    ('{"signaux": [', ""),
])
def test_l_explication_partielle_se_lit_dans_un_json_inacheve(brut, attendu):
    assert suivi.explication_partielle(brut) == attendu
