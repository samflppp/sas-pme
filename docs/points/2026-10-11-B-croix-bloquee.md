# Point B (Mouabd19) — page Direct : croix rouges pour une version bloquée — 2026-10-11

Demande de Mouabd19 pour la vidéo. **J'ai touché au dossier de A** (`plateforme/web/direct.py`),
c'est dit ici (règle 2).

## Fait
- Une version **bloquée après analyse** affiche une croix rouge sur « IA locale », « Politique »
  et « Signature et publication ». La publication dit « jamais publiée : la version est bloquée ».
- Les étapes d'avant (téléchargement, sandbox, contrôles) restent vertes : elles ont bien été
  faites.
- Une version bloquée **sans analyse** (par la veille ou par un humain) garde la règle de Sam :
  seule la dernière étape franchie est rouge.
- « À revoir » ne change pas : la dernière étape franchie est orange.

## Vérifié
- Nouveau test : vu rouge, vert, puis rouge à nouveau quand j'ai retiré le correctif. Suite
  complète : 746 verts.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Avec le trio (`B-trio-demo`) : `git pull` sur la plateforme puis relancer le web | vidéo | fait |
| A (Sam) | Relire `direct.py` (bloc « Bloquée après analyse ») | rien | ok |
