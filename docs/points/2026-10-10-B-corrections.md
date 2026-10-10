# Point B (Mouabd19) — réponses aux demandes de A (point A-m1) — 2026-10-10

## Fait
- **Archives reprises à la nouvelle tentative** (`traitement.py`) : une version approuvée non
  publiée reprend les archives de `dossier/nom/version`, vérifiées à l'analyse. Il n'y a plus de
  téléchargement à chaque tour. Si elles manquent et que le téléchargement échoue, la raison
  « téléchargement pour publication échoué : … » est écrite une seule fois, pas à chaque tour.
- **Typosquat branché** : `traiter()` appelle `controler_nom`, écrit les signaux (visibles sur la
  fiche) et les passe à la politique.
- **Politique déterministe, première règle** : un signal `BLOQUANT` bloque, un signal `FORT` met
  « à revoir », sinon la version est approuvée. La raison cite la preuve (« À revoir : « reqeusts »
  imite le paquet populaire « requests » »). Un typosquat n'est donc plus approuvé.
- `pyproject.toml` : `"plateforme.pipeline" = ["donnees/*.txt"]` dans `package-data`.
- 111 tests passent. Chaque correction a été cassée une fois pour voir son test au rouge.

## Disponible pour vous
- Les fiches des versions `a_revoir` portent un signal `typosquat` avec sa preuve
  (`preuve["extrait"]`, `preuve["cible"]`).

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| A | `demo/script.md` ligne 6 parle de « politique factice » : elle approuve toujours `requests`, mais elle n'est plus factice. À mettre à jour quand tu repasses dessus. | non | — |

## Réponses à vos demandes
- **(A, archives retéléchargées à chaque tour)** Corrigé, voir plus haut.
- **(A, `package-data`)** Ajouté.
- **(A, `controler_nom` non branché)** Branché, avec la première règle de la politique.
- **(A, dépendances résolues pendant la requête web)** Pas encore traité : décision à prendre avec
  Mouabd19, au début du M1.
- **(A, `SAS_DELAI`)** Pas encore traité : c'est la première tâche M1 de B. Le nom sera `SAS_DELAI`.

## Ensuite
- M1 : `SAS_DELAI`, veille OSV, contrôles statiques sur le code, LLM.
