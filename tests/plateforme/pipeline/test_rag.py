"""RAG (B, M2) : failles et paquets malveillants connus, index local, passages donnés au LLM.

Les embeddings d'Ollama sont remplacés ici par un plongement déterministe (sac de mots haché).
"""
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone

import httpx
import pytest
import respx

from commun.modeles import Ecosysteme, Etat, Niveau, RapportSandbox, Signal, Source, Version
from plateforme.db.acces import Base
from plateforme.pipeline import rag
from plateforme.pipeline.rag import construire, documents, index

P = Ecosysteme.PYPI
MAINTENANT = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
V = Version(ecosysteme=P, nom="demo-horodatage", version="1.2", publiee_le=MAINTENANT,
            detectee_le=MAINTENANT, etat=Etat.EN_ANALYSE)
OLLAMA = "http://ollama.test"

MAL = {
    "id": "MAL-2022-7421", "aliases": ["GHSA-hqmv-64pp-q4xw"],
    "summary": "Malicious code in ascii2text (PyPI)",
    "details": "\n---\n_-= Per source details. Do not edit below this line.=-_\n\n## Source: "
               "ghsa-malware (f4a1)\nSecurity researchers discovered a malicious package called "
               "`ascii2text` impersonating the PyPI package `art`.\n",
    "affected": [{"package": {"name": "ascii2text", "ecosystem": "PyPI"},
                  "database_specific": {"cwes": [{"cweId": "CWE-506",
                                                  "name": "Embedded Malicious Code"}]}}],
}
GHSA = {"id": "GHSA-aaaa-bbbb-cccc", "aliases": ["CVE-2026-1", "PYSEC-2026-9"],
        "summary": "Requests leaks Proxy-Authorization header", "details": "Details.",
        "affected": [{"package": {"name": "requests", "ecosystem": "PyPI"}}],
        "database_specific": {"cwe_ids": ["CWE-200"]}}
PYSEC = {"id": "PYSEC-2026-9", "aliases": ["CVE-2026-1", "GHSA-aaaa-bbbb-cccc"],
         "summary": "", "details": "Same flaw, from the PyPA database.",
         "affected": [{"package": {"name": "requests", "ecosystem": "PyPI"}}]}


def plonger(textes: list[str]) -> list[list[float]]:
    """Sac de mots haché sur 64 dimensions : deux textes qui partagent des mots sont proches."""
    sortie = []
    for t in textes:
        v = [0.0] * 64
        for mot in re.findall(r"[a-z0-9_]{3,}", t.lower()):
            v[int(hashlib.sha256(mot.encode()).hexdigest(), 16) % 64] += 1.0
        sortie.append(v if any(v) else [1.0] + [0.0] * 63)
    return sortie


def zip_osv(chemin, entrees):
    with zipfile.ZipFile(chemin, "w") as z:
        for e in entrees:
            z.writestr(f"{e['id']}.json", json.dumps(e))
    return chemin


# --- documents ----------------------------------------------------------------------------------

def test_un_paquet_malveillant_d_openssf_devient_un_document_lisible():
    d = documents.depuis_osv(MAL)
    assert d.ref == "MAL-2022-7421" and d.source == "openssf"
    assert "ascii2text" in d.texte and "impersonating the PyPI package `art`" in d.texte
    assert "CWE-506 (Embedded Malicious Code)" in d.texte
    assert "Per source details" not in d.texte and "## Source" not in d.texte


def test_un_avis_retire_n_est_pas_indexe():
    assert documents.depuis_osv({**GHSA, "withdrawn": "2026-01-01T00:00:00Z"}) is None


def test_un_document_est_borne():
    d = documents.depuis_osv({**GHSA, "details": "x" * 50_000})
    assert len(d.texte) <= documents.TAILLE_DOCUMENT


def test_l_export_osv_est_lu_sans_doublon_entre_alias(tmp_path):
    chemin = zip_osv(tmp_path / "all.zip", [PYSEC, GHSA, MAL])
    docs = list(documents.lire_osv(chemin))
    # PYSEC-2026-9 est le même avis que GHSA-aaaa-bbbb-cccc : un seul document, celui de GHSA.
    assert sorted(d.ref for d in docs) == ["GHSA-aaaa-bbbb-cccc", "MAL-2022-7421"]
    assert {d.ref: d.source for d in docs}["GHSA-aaaa-bbbb-cccc"] == "ghsa"
    assert "CWE-200" in next(d for d in docs if d.ref.startswith("GHSA")).texte


def test_le_referentiel_couvre_cwe_capec_et_attack():
    refs = {d.ref: d for d in documents.referentiel()}
    for ref in ("CWE-506", "CWE-522", "CAPEC-630", "CAPEC-538", "T1195.001", "T1552.001",
                "T1546.018"):
        assert ref in refs, ref
    assert all(d.texte and d.source in ("cwe", "capec", "attack", "rapport")
               for d in refs.values())


# --- index --------------------------------------------------------------------------------------

def test_l_index_rend_les_documents_les_plus_proches_et_borne_les_passages(tmp_path):
    ix = index.Index(tmp_path / "rag", plonger)
    ix.ajouter([documents.Document("A", "openssf", "vol de jetons aws credentials exfiltration "
                                   + "z" * 2000),
                documents.Document("B", "ghsa", "fuite d'en-tête proxy dans requests")])
    passages = ix.chercher("credentials aws exfiltration", n=1)
    assert [ref for ref, _ in passages] == ["A"]
    assert len(passages[0][1]) <= index.TAILLE_PASSAGE
    # Persistant : rouvert, l'index a gardé ses documents.
    assert index.Index(tmp_path / "rag", plonger).compter() == 2


def test_chroma_n_envoie_aucune_telemetrie(tmp_path):
    ix = index.Index(tmp_path / "rag", plonger)
    assert ix.client.get_settings().anonymized_telemetry is False


@respx.mock
def test_les_embeddings_viennent_d_ollama_local_avec_les_prefixes_de_nomic():
    route = respx.post(f"{OLLAMA}/api/embed").mock(
        return_value=httpx.Response(200, json={"embeddings": [[0.1, 0.2], [0.3, 0.4]]}))
    with httpx.Client() as client:
        v = index.vecteurs(["a", "b"], "search_document", client=client, url=OLLAMA,
                           modele="nomic-embed-text")
    assert v == [[0.1, 0.2], [0.3, 0.4]]
    corps = json.loads(route.calls[0].request.content)
    assert corps == {"model": "nomic-embed-text",
                     "input": ["search_document: a", "search_document: b"]}


# --- recherche pour une version -----------------------------------------------------------------

def signal(source, niveau, sorte, extrait, **plus):
    return Signal(ecosysteme=P, nom=V.nom, version=V.version, source=source, niveau=niveau,
                  sorte=sorte, preuve={"extrait": extrait, **plus})


SIGNAUX = [
    signal(Source.STATIQUE, Niveau.INFO, "domaine", "https://docs.python.org", domaine="docs.python.org"),
    signal(Source.STATIQUE, Niveau.BLOQUANT, "exfiltration", "_u.urlopen(URL, data=cles)"),
    signal(Source.SANDBOX, Niveau.BLOQUANT, "lit_leurre", "leurres lus : ~/.aws/credentials"),
]
RAPPORT = RapportSandbox(requetes_dns=["collecte.attaquant-demo.invalid"], connexions=[],
                         fichiers_sensibles=["~/.aws/credentials"],
                         leurres_lus=["~/.aws/credentials"], processus=[], code_sortie=0,
                         duree_s=3.0, delai_depasse=False)


def test_la_requete_decrit_la_version_par_ses_constats_les_plus_graves_d_abord():
    q = rag.requete(V, SIGNAUX, RAPPORT)
    assert q.startswith("pypi demo-horodatage")
    assert q.index("exfiltration") < q.index("domaine")
    assert "~/.aws/credentials" in q and "collecte.attaquant-demo.invalid" in q
    assert len(rag.requete(V, SIGNAUX * 200, RAPPORT)) <= rag.TAILLE_REQUETE


def test_les_passages_sont_les_cas_connus_proches(tmp_path):
    base = Base(str(tmp_path / "sas.db"))
    ix = index.Index(tmp_path / "rag", plonger)
    ix.ajouter([documents.Document("MAL-1", "openssf", "exfiltration aws credentials leurres"),
                documents.Document("GHSA-2", "ghsa", "bug d'affichage dans une table")])
    passages = rag.passages(base, V, SIGNAUX, RAPPORT, ix, n=1)
    assert [ref for ref, _ in passages] == ["MAL-1"]


def test_sans_index_le_llm_n_a_pas_de_passages_et_c_est_journalise(tmp_path):
    base = Base(str(tmp_path / "sas.db"))
    assert rag.passages(base, V, SIGNAUX, RAPPORT, None) == []
    assert base.journal()[-1].action == "rag_absent"


def test_un_index_en_panne_ne_casse_pas_l_analyse(tmp_path):
    base = Base(str(tmp_path / "sas.db"))

    class Panne:
        def chercher(self, requete, n):
            raise httpx.ConnectError("ollama arrêté")

    assert rag.passages(base, V, SIGNAUX, RAPPORT, Panne()) == []
    assert base.journal()[-1].action == "rag_indisponible"


def test_ouvrir_un_index_absent_ou_vide_donne_none(tmp_path):
    assert rag.ouvrir(tmp_path / "rien") is None
    index.Index(tmp_path / "vide", plonger)
    assert rag.ouvrir(tmp_path / "vide", plonger) is None


# --- construction -------------------------------------------------------------------------------

def test_la_construction_indexe_l_export_osv_et_le_referentiel(tmp_path, capsys):
    osv = zip_osv(tmp_path / "all.zip", [MAL, GHSA, PYSEC])
    code = construire.main(["--osv", str(osv), "--dossier", str(tmp_path / "rag")],
                           plonger=plonger)
    assert code == 0
    ix = index.Index(tmp_path / "rag", plonger)
    assert ix.compter() == 2 + len(documents.referentiel())
    assert "MAL-2022-7421" in {ref for ref, _ in ix.chercher("ascii2text art", n=3)}
    assert "documents indexés" in capsys.readouterr().out


def test_la_construction_peut_se_limiter_aux_paquets_malveillants(tmp_path):
    osv = zip_osv(tmp_path / "all.zip", [MAL, GHSA])
    construire.main(["--osv", str(osv), "--dossier", str(tmp_path / "rag"), "--malveillants"],
                    plonger=plonger)
    assert index.Index(tmp_path / "rag", plonger).compter() == 1 + len(documents.referentiel())
