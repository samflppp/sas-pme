# Point A (Sam) — `traiter()` en tâche de fond du web — 2026-10-10

## Fait
- **Tâche de fond** (`plateforme/web/fond.py`, `TacheDeFond`) : le web appelle
  `pipeline.traitement.traiter(base)` en boucle, sur un fil à lui, avec **sa** base.
  - Un seul fil : l'appel suivant part `intervalle` secondes **après la fin** du précédent. Deux
    appels ne se chevauchent jamais, même si un traitement dépasse 60 s.
  - Une erreur (passerelle injoignable, module de C absent) est écrite sur stderr ; la boucle continue.
  - Démarrée au lancement de l'application, arrêtée à sa fermeture (sans attendre la fin de
    l'intervalle).
- Réglages : `SAS_TRAITEMENT_INTERVALLE` (60 s par défaut, `0` coupe la tâche), `SAS_ARCHIVES`
  (dossier des archives, `archives` par défaut).
- 80 tests passent ; les cinq nouveaux ont été cassés une fois (sans `try`, `sleep` au lieu de
  l'attente interruptible, un fil par appel, pas d'arrêt à la fermeture).

## Disponible pour vous
- `creer_app(base, mot_de_passe, secret, demander=None, traiter=None, intervalle=60)` : sans
  `traiter`, aucune tâche de fond (c'est le cas des tests du web).
- En démo : `SAS_TRAITEMENT_INTERVALLE=5` pour voir les états changer vite.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C | `SAS_PASSERELLE_SSH` et `SAS_PASSERELLE_CLE` vont dans l'environnement du **service web** (uvicorn) sur la plateforme, puisque `traiter()` y tourne. | H3 | ok |
| B | Le délai de 3 jours est-il réglable par une variable d'environnement ? Le web appelle `traiter(base, dossier=...)` sans `delai` ; pour la démo il faudra un délai court. | démo | nom de la variable, ou j'ajoute `SAS_DELAI` côté web |

## Réponses à vos demandes
- **(B, « ne pas relancer `traiter` tant que l'appel précédent n'est pas fini »)** Oui : un seul
  fil, testé.
- **(B, « dossier des archives »)** `SAS_ARCHIVES`, `archives` par défaut.

## Ensuite
- M1 : comptes et rôles, file d'attente, décision humaine.
