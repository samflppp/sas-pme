"""Vérification du vrai LLM sur la démo (B) : format respecté, durée, phrase, pour 1.1 et 1.2.

Ici Ollama est simulé ; sur la plateforme : `python3 -m mesure.llm_demo`.
"""
import importlib.util
import json
from pathlib import Path

import httpx
import respx

RACINE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("llm_demo", RACINE / "mesure" / "llm_demo.py")
llm_demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(llm_demo)

OLLAMA = "http://ollama.test"
BONNE = {"signaux": [{"niveau": "fort", "sorte": "vol_de_jetons", "extrait": "lit ~/.aws"}],
         "explication": "La version lit des identifiants AWS puis appelle un domaine inconnu.",
         "refs_rag": []}


def repondre(contenus):
    reponses = iter(contenus)

    def suite(request):
        c = next(reponses)
        texte = c if isinstance(c, str) else json.dumps(c)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": texte}})
    return suite


@respx.mock
def test_les_deux_versions_de_demo_passent_avec_leurs_vrais_constats(tmp_path):
    route = respx.post(f"{OLLAMA}/api/chat").mock(side_effect=repondre([BONNE, BONNE]))
    with httpx.Client() as client:
        essais = llm_demo.verifier(client, OLLAMA, "qwen2.5-coder:7b", tmp_path)
    assert [e.version for e in essais] == ["1.1", "1.2"]
    assert all(e.conforme and e.duree_s >= 0 for e in essais)
    assert essais[1].signaux == ["fort vol_de_jetons"]
    assert essais[1].explication.startswith("La version lit")
    prompt_11, prompt_12 = (json.loads(c.request.content) for c in route.calls)
    assert prompt_12["model"] == "qwen2.5-coder:7b"
    texte_12 = prompt_12["messages"][1]["content"]
    # La 1.2 arrive avec les vrais constats statiques et le rapport attendu de la sandbox v1.
    assert "exfiltration" in texte_12 and "lit_leurre" in texte_12
    assert "exfiltration" not in prompt_11["messages"][1]["content"]


@respx.mock
def test_une_reponse_hors_schema_rend_l_essai_non_conforme_et_le_code_de_sortie_1(tmp_path, capsys):
    respx.post(f"{OLLAMA}/api/chat").mock(side_effect=repondre([BONNE, "pas du JSON"]))
    code = llm_demo.main(["--url", OLLAMA, "--modele", "qwen2.5-coder:7b"], dossier=tmp_path)
    sortie = capsys.readouterr().out
    assert code == 1
    assert "1.1" in sortie and "conforme" in sortie and "HORS SCHÉMA" in sortie


@respx.mock
def test_tout_conforme_donne_le_code_de_sortie_0(tmp_path, capsys):
    respx.post(f"{OLLAMA}/api/chat").mock(side_effect=repondre([BONNE, BONNE]))
    assert llm_demo.main(["--url", OLLAMA, "--modele", "m"], dossier=tmp_path) == 0
    assert "La version lit" in capsys.readouterr().out
