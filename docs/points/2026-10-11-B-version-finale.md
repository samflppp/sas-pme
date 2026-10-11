# Point B (Mouabd19) — version finale du site, livrée au jury — 2026-10-11

Décision de Mouabd19 : le produit passe en production. Aucune trace de développement ne doit
rester sur le site. **J'ai touché aux dossiers de A** (`plateforme/web/`) **et de C**
(`plateforme/signature/`, `infra/domaine/vitrine/`). C'est dit ici (règle 2).

## Plateforme (demo.pipelad.tech)
- **Pages de développeur fermées** : `/docs`, `/redoc` et `/openapi.json` (Swagger de FastAPI)
  répondent 404.
- Menu latéral : la section « Démo » devient « **Paquets** » (Demandes, Direct, Catalogue).
- Console npm : « l'agent de la démo… » devient « l'installation automatique couvre les paquets
  pip ».
- Message d'erreur de la signature : « M0 : pip seulement » devient « écosystème non pris en
  charge par ce chemin ».

## Vitrine (pipelad.tech)
- Les boutons « Ouvrir la démo » deviennent « **Accéder à la plateforme** ».
- Le pied de page ne dit plus « projet de hackathon ». « Infrastructure de démo » devient
  « infrastructure de référence ».
- **Mesure finale** à la place de « mesure finale en cours » :
  - 80 % (103 sur 128), pipeline complet ;
  - 0 fausse alerte sur 98 ;
  - mesure du 2026-10-11.
- Tableau de la concurrence : Pipelad couvre « pip, npm ».

## Vérifié
- Tests neufs :
  - les pages de développeur sont fermées ;
  - aucun « Démo », « M0 », « stub », « hackathon » ni « MVP » dans six pages de l'interface ;
  - la vitrine sans trace de développement, avec la mesure finale.
- Vus rouges, puis le mot remis une fois : le test retombe au rouge. Suite complète : 767 verts.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Plateforme : `git pull`, puis relancer `~/h16.sh` ; vitrine : relancer `infra/aws/domaine.sh` | livraison au jury | fait |
| A (Sam) | Relire les libellés (menu « Paquets », boutons de la vitrine) | livraison | ok |
