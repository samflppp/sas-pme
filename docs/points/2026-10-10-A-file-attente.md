# Point A (Sam) — M1 : file d'attente avec compte à rebours — 2026-10-10

## Fait
- Lu les points B-delai, B-cible et C-windows.
- **Séance AWS avec C sur le `main` à jour** (message à C, suivi en entier) : comptes `mouabd` et
  `steusso` créés, `requests` republié, `verifier_h3.sh` relancé.
- **Page « File d'attente »** (`/file-attente`, tous les rôles) :
  - versions `nouvelle` et `en_attente`, avec le temps restant avant l'analyse :
    `publiee_le + pypi.delai()` (donc `SAS_DELAI` en démo), ordre de fin d'attente ;
  - décompte en direct dans le navigateur ; sans JavaScript, le temps calculé par le serveur ;
  - attente échue : « au prochain tour » ;
  - sections « En analyse », « À revoir » et « Bloquées », avec la raison de chaque version ;
  - un `SAS_DELAI` illisible s'affiche en erreur sur la page (pas d'erreur 500, aucun délai deviné).
- `Base.lister_avec_raison(etats)` (`docs/contrats.md` § 2).
- `demo/script.md` : `SAS_DELAI=120`, et la phrase sur le délai corrigée (demande de B).
- 188 tests passent ; les 11 nouveaux ont été cassés une fois (délai fixe, rebours depuis la
  détection, ordre de la base inversé, `ValueError` non rattrapée, format des durées).

## Disponible pour vous
- La file montre ce qui entrera par la veille de B, sans rien à changer chez A.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| B | Toujours ouverte : la signature de `pipeline.decision_humaine(...)` (point A-comptes). Je propose `decision_humaine(base, eco, nom, version, etat: Etat, raison: str, acteur: str)`. | M1 (décision humaine) | oui / autre |

## Réponses à vos demandes
- **(B, `SAS_DELAI=120` et phrase sur le délai dans `demo/script.md`)** Fait.
- **(B, la version qui attend arrive par la veille)** Noté ; la file l'affichera telle quelle.
- **(C, `demo/forger.sh` plutôt qu'un bouton)** Confirmé.

## Ensuite
- Décision humaine (dès la réponse de B), fiche complète, page du journal.
