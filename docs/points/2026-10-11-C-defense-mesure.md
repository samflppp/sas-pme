# Point C — fiche de défense : mesure finale reportée (à la place de A) — 2026-10-11

## Fait
C m'a demandé de faire ce travail à la place de A. Ce sont les demandes de B à A
(`B-mesure-finale`, `B-mesure-close`), dans `docs/defense.md` :
- **§ 3 :**
  - le tableau final à trois lignes (73 % → 80 % → 80 %, 0 fausse alerte sur 98) ;
  - comment il est mesuré, avec la phrase pour le jury ;
  - la lecture honnête : la sandbox paie ; le LLM n'ajoute aucune détection, et c'est voulu
    (5 versions sur 226 où il pouvait changer le verdict) ; la réponse au premortem ; les
    25 manquées, dont ultralytics, et la limite des dépendances.
  - La ligne « nom seul, OpenSSF, 3 % » est gardée en comparaison, avec sa date.
- **§ 4, « Un paquet peut détecter la sandbox » :** une version qui ne s'importe pas sans ses
  dépendances n'est observée qu'à l'installation (ultralytics).
- **§ 6 :** la limite des dépendances, chiffrée (58 saines sur 98 observées à l'import ; 12
  manquées sur 25 en échec d'import). Idée notée, pas codée.
- **§ 7 :** la sandbox avec les dépendances déjà approuvées, dans la suite prévue.
- **§ 2 et § 10 :** 551 tests verts au 2026-10-11 (au lieu de 531).

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| A (Sam) | Relire le § 3 réécrit ; il reste à toi le deck | H22 | ok / retouches |
| B | Vérifier que la lecture du § 3 dit bien ta mesure | H22 | ok / retouches |
