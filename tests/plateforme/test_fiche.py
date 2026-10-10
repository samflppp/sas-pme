from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from commun.modeles import (
    Ecosysteme, Etat, Niveau, RapportSandbox, Signal, Source, Verdict, Version,
)
from plateforme.db.acces import Base
from plateforme.web.app import creer_app

T0 = datetime(2026, 10, 9, 22, 15, tzinfo=timezone.utc)
MDP = "mot-de-passe-de-test"
ECO = Ecosysteme.PYPI


@pytest.fixture
def base(tmp_path) -> Base:
    return Base(str(tmp_path / "sas.db"))


@pytest.fixture
def client(base) -> TestClient:
    c = TestClient(creer_app(base=base, mot_de_passe=MDP, secret="s", demander=lambda e, n: None))
    c.post("/connexion", data={"identifiant": "admin", "mot_de_passe": MDP})
    return c


def signal(source, niveau, sorte, **preuve) -> Signal:
    structure = preuve.pop("structure", True)
    return Signal(ecosysteme=ECO, nom="colorama-utils", version="1.1", source=source,
                  niveau=niveau, sorte=sorte, preuve=preuve, structure=structure)


def version_bloquee(base: Base) -> None:
    for numero, etat in (("1.0", Etat.PUBLIEE), ("1.1", Etat.EN_ATTENTE)):
        base.enregistrer_version(Version(ecosysteme=ECO, nom="colorama-utils", version=numero,
                                         publiee_le=T0, detectee_le=T0, etat=etat))
    base.changer_etat(ECO, "colorama-utils", "1.1", Etat.EN_ANALYSE, "analyse en cours")
    signaux = [
        signal(Source.STATIQUE, Niveau.MOYEN, "lit_secrets", fichier="setup.py", ligne=38,
               extrait="os.environ TOKEN"),
        signal(Source.VEILLE, Niveau.FORT, "article", structure=False,
               extrait="Malware found in colorama-utils 1.1", url="https://chercheur.example/billet"),
        signal(Source.SANDBOX, Niveau.BLOQUANT, "lit_leurre", extrait="GITHUB_TOKEN lu puis envoyé"),
        signal(Source.LLM, Niveau.INFO, "remarque", extrait="<script>alert(1)</script>",
               url="javascript:alert(1)"),
    ]
    for s in signaux:
        base.ajouter_signal(s)
    base.enregistrer_rapport_sandbox(ECO, "colorama-utils", "1.1", RapportSandbox(
        requetes_dns=["exfil.demo.invalid"] * 6, connexions=["exfil.demo.invalid:443"] * 6,
        fichiers_sensibles=[], leurres_lus=["GITHUB_TOKEN"], processus=["pip", "python"],
        code_sortie=0, duree_s=64.2, delai_depasse=False))
    base.enregistrer_verdict(ECO, "colorama-utils", "1.1", Verdict(
        etat=Etat.BLOQUEE, raison="Cette version vole les jetons d'accès dès son installation.",
        signaux=signaux, explication_llm="Technique connue de vol d'identifiants.",
        refs_rag=["CWE-506", "MAL-2024-9921"]))
    base.changer_etat(ECO, "colorama-utils", "1.1", Etat.BLOQUEE, "Bloquée : leurre lu.")


def fiche(client) -> str:
    r = client.get("/versions/pypi/colorama-utils/1.1")
    assert r.status_code == 200
    return r.text


def test_la_phrase_le_verdict_et_qui_a_decide(base, client):
    version_bloquee(base)
    t = fiche(client)
    assert "Cette version vole les jetons" in t and "Technique connue" in t and "CWE-506" in t
    assert "Décision prise par la politique (code)" in t


def test_les_signaux_les_plus_graves_d_abord(base, client):
    version_bloquee(base)
    t = fiche(client)
    rangs = [t.index(x) for x in ("GITHUB_TOKEN lu", "Malware found", "os.environ TOKEN",
                                  "&lt;script&gt;")]
    assert rangs == sorted(rangs)


def test_la_preuve_dit_fichier_ligne_et_lien(base, client):
    version_bloquee(base)
    t = fiche(client)
    assert "setup.py:38" in t
    assert 'href="https://chercheur.example/billet"' in t
    assert "source libre" in t  # un article ne bloque pas seul


def test_une_preuve_ne_peut_injecter_ni_balise_ni_lien_javascript(base, client):
    version_bloquee(base)
    t = fiche(client)
    assert "<script>alert(1)</script>" not in t
    assert 'href="javascript:' not in t


def test_la_sandbox_compte_les_repetitions(base, client):
    version_bloquee(base)
    t = fiche(client)
    assert "exfil.demo.invalid (×6)" in t and "exfil.demo.invalid:443 (×6)" in t
    assert "GITHUB_TOKEN" in t and "64.2 s" in t


def test_l_historique_de_la_version_vient_du_journal(base, client):
    version_bloquee(base)
    t = fiche(client).split("<h2>Historique</h2>")[1]
    etapes = [t.index(x) for x in ("version_detectee", "analyse en cours", "verdict",
                                   "Bloquée : leurre lu.")]
    assert etapes == sorted(etapes)


def test_les_autres_versions_du_paquet(base, client):
    version_bloquee(base)
    t = fiche(client).split("<h2>Autres versions</h2>")[1]
    assert 'href="/versions/pypi/colorama-utils/1.0"' in t and "publiee" in t
    assert 'href="/versions/pypi/colorama-utils/1.1"' not in t


def test_une_version_sans_analyse(base, client):
    base.enregistrer_version(Version(ecosysteme=ECO, nom="requests", version="2.32.5",
                                     publiee_le=T0, detectee_le=T0, etat=Etat.EN_ATTENTE))
    t = client.get("/versions/pypi/requests/2.32.5").text
    assert "Aucun signal" in t and "Pas encore passée en sandbox" in t
    assert "Décision prise par la politique" not in t
