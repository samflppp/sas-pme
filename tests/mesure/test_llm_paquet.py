"""Vérifier le vrai LLM sur n'importe quelle version de PyPI (B, H16) : `python -m mesure.llm_paquet`.

Ici PyPI et Ollama sont simulés. Le cas rejoué est celui de la répétition H16 (point C) : pour
certifi, le LLM recopiait un passage du RAG comme « preuve ».
"""
import hashlib
import importlib.util
import io
import json
import zipfile
from pathlib import Path

import httpx
import respx

RACINE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("llm_paquet", RACINE / "mesure" / "llm_paquet.py")
llm_paquet = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(llm_paquet)

OLLAMA, PYPI = "http://ollama.test", "http://pypi.test"


def roue() -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        z.writestr("certifi/__init__.py", "def where():\n    return '/etc/ssl/cacert.pem'\n")
    return tampon.getvalue()


def simuler_pypi():
    octets = roue()
    fichier = {"filename": "certifi-2026.7.22-py3-none-any.whl", "packagetype": "bdist_wheel",
               "url": f"{PYPI}/f/certifi.whl", "yanked": False,
               "digests": {"sha256": hashlib.sha256(octets).hexdigest()},
               "upload_time_iso_8601": "2026-07-22T00:00:00.000000Z"}
    respx.get(f"{PYPI}/pypi/certifi/json").respond(
        json={"info": {"name": "certifi"}, "releases": {"2026.7.22": [fichier]}})
    respx.get(f"{PYPI}/f/certifi.whl").respond(content=octets)


def ollama(signal_niveau="fort", extrait="PTH file… payload stored in chunks in DNS records"):
    contenu = {"signaux": [{"niveau": signal_niveau, "sorte": "pth_suspect", "extrait": extrait}],
               "explication": "Rien de clair.", "refs_rag": []}
    return respx.post(f"{OLLAMA}/api/chat").respond(
        json={"message": {"role": "assistant", "content": json.dumps(contenu)}})


@respx.mock
def test_la_fausse_alerte_de_certifi_redescend_et_la_politique_approuve(tmp_path):
    simuler_pypi()
    route = ollama()
    with httpx.Client() as client:
        essais = llm_paquet.verifier(["certifi==2026.7.22"], client, OLLAMA, "qwen2.5-coder:7b",
                                     tmp_path, pypi_base=PYPI)
    (e,) = essais
    assert (e.nom, e.version, e.conforme) == ("certifi", "2026.7.22", True)
    assert e.signaux_llm == ["moyen pth_suspect (non ancré : redescendu de fort)"]
    assert e.verdict == "approuvee"
    # Le LLM a reçu le vrai code du paquet, lu comme donnée (jamais exécuté).
    assert "certifi" in json.loads(route.calls.last.request.content)["messages"][1]["content"]


@respx.mock
def test_la_sortie_dit_le_verdict_et_le_code_de_retour(tmp_path, capsys, monkeypatch):
    simuler_pypi()
    ollama()
    monkeypatch.setattr(llm_paquet.pypi, "BASE", PYPI)
    code = llm_paquet.main(["certifi==2026.7.22", "--url", OLLAMA], dossier=tmp_path)
    sortie = capsys.readouterr().out
    assert code == 0
    assert "certifi 2026.7.22 : verdict approuvee" in sortie
    assert "non ancré" in sortie


def test_une_version_mal_ecrite_est_refusee():
    assert llm_paquet.main(["certifi"]) == 2
