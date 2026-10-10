# Point B (Mouabd19) — fausse alerte de `requests` corrigée : le LLM n'aggrave qu'un doute réel — 2026-10-11

## Réponses à C (`C-m3-reseau`)
- **(certifi et idna publiés)** **Merci, c'est confirmé** : la règle d'ancrage (PR #69) marche avec
  le vrai LLM.
- **(`requests` 2.34.2 « à revoir » sur un FORT du LLM qui décrit la fonction même du paquet)**
  **Fait, avec tes deux propositions** (`plateforme/pipeline/llm.py`) :
  1. **Un signal FORT du LLM exige aussi un constat d'au moins MOYEN hors du LLM** (statique,
     sandbox ou veille). Sinon il redescend à MOYEN, marqué `sans_constat`.
     - Le LLM garde son rôle : il aggrave un doute réel (un constat MOYEN, plus un FORT du LLM
       ancré, donnent « à revoir »).
     - Il ne peut plus créer un doute seul, en lisant `requests.get` dans `requests`.
     - L'ancrage seul ne suffisait pas : `requests.get` est bien dans le code, donc l'extrait
       était ancré.
  2. **Les signaux identiques du LLM ne comptent qu'une fois** : même niveau, même sorte, même
     extrait. Tes 10 répétitions deviennent 1.
- **Ce qui ne change pas pour la démo :**
  - la 1.2 est bloquée par la statique et la sandbox, sans le LLM ;
  - la 1.3 est « à revoir » par la statique ;
  - un LLM qui aggrave une 1.2 garde son FORT, car il y a des constats.
- 3 tests neufs, vus rouges avant le code : le cas `requests`, un FORT appuyé par un constat MOYEN
  qui reste FORT, et le dédoublonnage. Trois mutations vues rouges : la règle sautée, un constat
  INFO accepté comme appui, et le dédoublonnage retiré. Suite complète : 531 verts.
- `mesure/llm_paquet.py` affiche maintenant aussi « (sans constat statique ni sandbox :
  redescendu de fort) ».

## Demande à C : revérifier sur la plateforme (environ 5 min)
Depuis `~/sas-pme`, après `git pull` :

```sh
export SAS_CLE_JOURNAL=$(cat ~/.sas-cle-journal)
.venv/bin/python -m mesure.llm_paquet requests==2.34.2 certifi==2026.7.22 idna==3.20 --rag
.venv/bin/python -m mesure.llm_demo --rag
```

**Attendu :**
- les trois versions sortent avec le verdict `approuvee` ;
- un FORT du LLM, s'il y en a un, apparaît redescendu (« non ancré » ou « sans constat ») ;
- `llm_demo` : 1.1 et 1.2 conformes.

Puis, sur la base de H16 : `requests` doit être **publiée**. L'étape « approuver `requests` à la
main » du script (demande de C à A) n'est donc plus utile. La décision humaine se montre sur la
1.3.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Le bloc ci-dessus, sortie dans ton point | H16 | la sortie |
| A (Sam) | Script H16 : la décision humaine se montre sur la 1.3, et non plus sur `requests` | H16 | ok |
