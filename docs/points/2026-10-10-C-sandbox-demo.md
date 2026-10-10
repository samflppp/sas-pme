# Point C (STEUSSO) — sandbox v1 sur la version piégée de démo de B — 2026-10-10

## Fait
- Passé dans la sandbox (et nulle part ailleurs) `demo-horodatage`, construit par
  `demo/paquets/faux_pypi.py`, avec le module `demo_horodatage` :

  | Archive | requetes_dns | connexions | leurres_lus | processus |
  |---|---|---|---|---|
  | 1.1 wheel / sdist | — | — | — | — |
  | 1.2 wheel | `collecte.attaquant-demo.invalid` | `…invalid:443` | `~/.aws/credentials` | — |
  | 1.2 sdist | `collecte.attaquant-demo.invalid` | `…invalid:443` | `~/.aws/credentials` | — |

  `fichiers_sensibles` vaut `['~/.aws/credentials']` pour la 1.2. Le faux DNS répond aussi pour
  `.invalid`.
- Bruit retiré : pendant l'installation, les commandes que pip lance lui-même (`uname -rs`,
  `lsb_release -a`, ses crochets de construction d'un sdist) ne sont pas comptées comme
  `processus`. Ces commandes exactes seulement : un `setup.py` qui lance autre chose reste visible.

## Réponses à vos demandes
- **(B, « pas les résolutions de la sandbox elle-même dans `requetes_dns` »)** C'est le cas :
  l'installation se fait sans réseau, et seules les résolutions du paquet sont notées. La 1.1
  donne `[]`.
- **(B, « la commande complète dans `processus` »)** Oui : la liste d'arguments jointe, ou la chaîne
  passée au shell (`os.system`, `shell=True`).
- **(B, `import demo_horodatage` avec le leurre `~/.aws/credentials`, DNS pour `.invalid`)** Oui,
  voir le tableau.
- **(B, temps de réponse d'Ollama)** À la prochaine séance AWS : j'installe Ollama sur la
  plateforme et je lance `pytest -m ollama tests/plateforme/pipeline/test_llm.py`.

## Ensuite
- Ollama dans `installer.sh` (plateforme, `qwen2.5-coder:3b` et `nomic-embed-text`), puis une séance
  AWS pour la répétition H10 complète.
