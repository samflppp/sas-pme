# Point B (Mouabd19) — console serveur : succès ou échec selon le verdict — 2026-10-11

Demande de Mouabd19 pour la vidéo : la console « Serveur » de la page Direct doit finir sur un
message de succès (vert) ou d'échec (orange ou rouge), selon le verdict de la pipeline.
**J'ai touché au dossier de A** (`plateforme/web/direct.py`, gabarit, `direct.js`), c'est dit
ici (règle 2).

## Fait
Dernière ligne de la console, tirée de l'état de la version demandée :

| Verdict | Ligne |
|---|---|
| publiée | ✓ (vert) « … vérifiée, signée et publiée : installation autorisée sur le serveur », puis « ✓ … installée » quand le serveur l'a téléchargée |
| à revoir | ✗ (rouge) « installation refusée : … est à revoir, un humain doit trancher… » |
| bloquée | ✗ (rouge) « installation refusée : … est bloquée par la pipeline, le serveur ne la recevra jamais » |
| révoquée | ✗ (rouge) « installation refusée : … a été révoquée et retirée de la passerelle » |
| en cours d'analyse | rien de neuf : « le serveur réessaie… » ou « en attente… » |

- Elle vaut pour pip **et npm**.
- Sur un refus, la ligne « ↳ … sur PyPI : … Pas servie » disparaît : elle disait la même chose.

## Vérifié
- 5 tests neufs. Un test de A est adapté : la console dit maintenant « installation refusée »
  plutôt que « aucune version servie ». Message retiré une fois : les tests sont passés au rouge.
  Suite complète : 761 verts.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | `git pull` sur la plateforme et relancer le web (`~/h16.sh`), avec #121 et #122 | vidéo | fait |
| A (Sam) | Relire le message de la console | rien | ok |
