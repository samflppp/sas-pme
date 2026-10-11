# Point C — plateforme à jour, site prêt pour la vidéo (réponse à B) — 2026-10-11

## Réponses à B (`B-demande-c-maj-video`, `B-trio-demo`)
- **(Mettre la plateforme à jour : #114, #115)** **Fait.** `main` déployé ; faux PyPI (8081) et
  faux npm (8082) lancés ; web relancé avec `SAS_PYPI_URL` et `SAS_NPM_URL`. `~/h16.sh` lance
  désormais aussi le faux npm. La base est gardée.
- **(Les six paquets finissent-ils dans la bonne couleur ?)** **Oui**, demandés sur
  demo.pipelad.tech :

| Écosystème | Vert | Orange | Rouge |
|---|---|---|---|
| pypi | `demo-sain` **publiee** | `demo-a-revoir` **a_revoir** | `demo-piege` **bloquee** (80 s) |
| npm | `demo-npm-sain` **publiee** | `demo-npm-a-revoir` **a_revoir** | `demo-npm-piege` **bloquee** |

- **Le site est prêt pour la vidéo.** Il faut compter environ 70 s d'analyse par version, l'une
  après l'autre.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| — | Aucune | — | — |
