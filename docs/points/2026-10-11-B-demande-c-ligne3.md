# Point B (Mouabd19) — à C : lancer la ligne 3 de la mesure finale sur AWS — 2026-10-11

## Pourquoi c'est à toi
- La mesure finale (M3) a trois lignes : contrôles seuls ; + sandbox ; + LLM/RAG.
- Les lignes 1 et 2 sont sur `main` (PR #82) : **93 puis 103 / 128 détectées, 0 / 98 fausse
  alerte**.
- La ligne 3 demande Ollama (`qwen2.5-coder:7b`) et l'index du RAG. Les deux ne sont que sur la
  plateforme AWS : mon environnement ne peut pas télécharger les modèles.
- **C'est le dernier chiffre qui manque à la diapositive de mesure, au deck de A et à la fiche de
  défense (H22).**

## Ce qu'il faut faire (environ 15 min, dont 5 de LLM)
Sur la plateforme, depuis `~/sas-pme` :

```sh
git pull
export SAS_CLE_JOURNAL=$(cat ~/.sas-cle-journal)
D=~/mesure && mkdir -p $D/cache/rapports && cp mesure/rapports_sandbox/*.json $D/cache/rapports/
git clone --depth 1 --filter=blob:none --no-checkout \
    https://github.com/DataDog/malicious-software-packages-dataset $D/dd
.venv/bin/python -I -c "import json; print('\n'.join(e['echantillon'] for e in json.load(open('demo/corpus/corpus_code.json'))['malveillants']))" \
    | xargs git -C $D/dd checkout HEAD --
.venv/bin/python -I mesure/mesurer.py --echantillons $D/dd --cache $D/cache --llm
```

**Sans risque :**
- les échantillons sont lus, jamais exécutés par cette commande ;
- la sandbox n'est pas relancée : ses rapports viennent de `mesure/rapports_sandbox/` ;
- le LLM ne reçoit que des constats et des rapports, et n'est interrogé que sur 5 versions.

**Attendu à la fin :**
- un tableau à trois lignes, dont les lignes 1 et 2 sont identiques à `main` (93 et 103 / 128,
  0 / 98) ;
- la note « LLM interrogé sur 5 versions ».

## Ce que tu me renvoies
- **Le plus simple :** commiter `mesure/resultats.md`, réécrit par la commande, dans une PR à toi,
  et me prévenir.
- **Sinon :** coller dans ton point le tableau et les lignes « Arrêtées en plus » de la section
  « 3. + LLM/RAG ».
- **En cas d'échec :** colle la dernière erreur telle quelle. Par exemple : « Index du RAG
  absent », une erreur de clé du journal, ou Ollama injoignable.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Lancer le bloc ci-dessus et renvoyer `mesure/resultats.md` (ou son tableau) | H22 : mesure, deck, fiche de défense | le tableau |
