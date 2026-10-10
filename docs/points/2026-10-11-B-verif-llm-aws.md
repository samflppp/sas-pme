# Point B (Mouabd19) — à C : vérifier sur AWS la correction des fausses alertes du LLM — 2026-10-11

## Pourquoi
- La règle d'ancrage (PR #69) corrige les fausses alertes de certifi et d'idna vues à ta
  répétition (`C-h16-repetition`). Un signal FORT du LLM sans preuve tirée du paquet redescend à
  MOYEN.
- Je l'ai testée en simulant Ollama, et j'ai joué tout le déroulé en local (`B-essai-local`).
- Mais **le vrai LLM n'existe que sur la plateforme AWS** : le réseau de mon environnement bloque
  le téléchargement des modèles. C'est donc là qu'il faut la vérifier.

## Fait
- **`mesure/llm_paquet.py`** : il vérifie le vrai LLM sur **n'importe quelle version de PyPI**, en
  une commande, sans base ni web. Pour chaque version :
  - il télécharge depuis PyPI et vérifie le sha256 ;
  - il lance les vrais contrôles statiques (le code est lu, jamais exécuté) ;
  - il appelle le LLM avec le RAG, exactement comme le pipeline ;
  - il affiche chaque signal du LLM (et s'il a été redescendu), puis le **verdict de la
    politique**.
- 3 tests, Ollama et PyPI simulés, vus rouges avant le code. Ils rejouent le cas certifi : la
  « preuve » est un passage du RAG recopié, le signal sort MOYEN, et le verdict est
  « approuvee ». Deux mutations vues rouges : sans la règle d'ancrage, et sans la mention
  « non ancré » à l'affichage. Suite complète : 528 verts.

## Demande à C : le bloc à lancer sur la plateforme (environ 5 min)
Depuis `~/sas-pme`, après `git pull` :

```sh
export SAS_CLE_JOURNAL=$(cat ~/.sas-cle-journal)
.venv/bin/python -m mesure.llm_paquet certifi==2026.7.22 idna==3.20 --rag
.venv/bin/python -m mesure.llm_demo --rag
```

**Ce que j'attends :**

| Ligne | Attendu |
|---|---|
| `certifi 2026.7.22 : verdict …` | `approuvee` ; un signal FORT du LLM sans preuve apparaît en `moyen … (non ancré : redescendu de fort)` |
| `idna 3.20 : verdict …` | `approuvee`, même chose |
| `llm_demo`, 1.1 | conforme, aucun signal FORT |
| `llm_demo`, 1.2 | conforme ; ses signaux FORT restent FORT, car ils citent `~/.aws` ou le domaine de l'attaquant ; `cite :` au moins une référence |

**Si certifi ou idna sortent encore « a_revoir » :** colle la ligne `LLM :` telle quelle. Elle
dit quel extrait le LLM a cité et pourquoi la règle l'a gardé FORT. Je corrige dans l'heure.

Ensuite, pendant le H16, avec une base neuve : `requests` et ses dépendances doivent être toutes
**publiées**. Plus aucune ne doit être « à revoir ».

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Lancer le bloc ci-dessus sur la plateforme et coller sa sortie dans ton point | H16 | la sortie |
