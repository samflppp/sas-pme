# Point C (STEUSSO) — test Windows du traceur, Ollama dans l'installation — 2026-10-10

## Fait
- `test_le_traceur_note_fichiers_processus_et_reseau` lance maintenant
  `[sys.executable, "-c", "pass", "marqueur-sas"]` au lieu de `true`. Il passe sous Windows et
  vérifie toujours que le processus est noté (test cassé une fois).
- `installer.sh`, étape 9 : il installe Ollama sur la plateforme (`127.0.0.1:11434`, rien
  d'ouvert dehors) et tire `qwen2.5-coder:7b`, `qwen2.5-coder:3b` et `nomic-embed-text`. Le disque
  de la plateforme (100 Go) suffit.
- `infra/README.md` : le 7B par défaut, le 3B en repli.

## Réponses à vos demandes
- **(A et B, test Windows)** Corrigé, sans `skipif`.
- **(A, B, modèle 7B)** Les deux modèles sont tirés à l'installation.
- **(A, B : `mesure.llm_demo` 7B et 3B, `pytest -m ollama`, durées et phrases)** Je les lance à la
  prochaine séance AWS, et je colle les sorties dans mon point.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| **A** | Créneau pour la séance AWS de répétition H10 complète. Je suis disponible. Il faut prévoir environ 15 min d'installation de plus (Docker, Ollama, 7 Go de modèles). | H10 | créneau |

## Ensuite
- Séance AWS : installation, mesures du LLM, répétition H10 (publication signée, version piégée
  bloquée, `forger.sh` refusé).
