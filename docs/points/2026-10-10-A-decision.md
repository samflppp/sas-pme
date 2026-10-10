# Point A (Sam) — M1 : décision humaine — 2026-10-10

## Fait
- **Boutons « Approuver » et « Bloquer »** sur la fiche d'une version `a_revoir`, pour les admins
  seulement. Une raison est obligatoire (500 caractères au plus), elle est inscrite au journal.
- `POST /decision` appelle `pipeline.decision_humaine(base, eco, nom, version, etat, raison,
  acteur)` (B), avec l'identifiant de l'admin comme acteur. Ensuite, retour à la fiche : le
  nouvel état, la preuve « admin : raison » et l'historique sont visibles.
- Les refus de B (`ValueError` : raison vide, version déjà tranchée…) s'affichent en rouge sur
  la fiche (400), pas en erreur 500. Une version inconnue → 404. Un dev → 403.
- Le formulaire disparaît dès que la version est tranchée.
- `creer_app(..., decider=...)` pour les tests ; par défaut, le vrai pipeline, importé au
  premier clic seulement.
- 299 tests passent. Les 9 nouveaux tests ont été rouges avant le code ; chaque garde (rôle,
  état `a_revoir`, raison nettoyée, 404) a été cassée une fois pour voir son test tomber.

## Disponible pour vous
- Démo H10 : une version à revoir → l'admin l'approuve ou la bloque avec une raison → la fiche
  et le journal le montrent.

## Demandes
Aucune.

## Ensuite
- M1 de A terminé. Aide à l'intégration H10 (démo de bout en bout avec la version piégée).
