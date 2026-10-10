# Point A (Sam) — correctifs A1 et A2 de la relecture de B — 2026-10-10

## Fait
- **A2 : un inventaire refusé ne bloque plus la base.** `enregistrer_inventaire` fait un `ROLLBACK`
  sur toute erreur et relève l'exception. L'ancien instantané reste en place, et les écritures
  suivantes (journal compris) sont bien validées. Test : deux entrées en double, puis une écriture
  vue depuis une autre connexion.
- **A1 : le journal est signé en HMAC-SHA256** avec une clé hors de la base, `SAS_CLE_JOURNAL`
  (32 caractères au moins). Sans elle, `Base(...)` lève `RuntimeError` : la plateforme ne démarre
  pas. Test : l'attaque de B (`DROP TRIGGER`, « bloquée » réécrit en « approuvée », chaîne
  recalculée en sha256) est maintenant détectée à l'entrée n° 1 ; une autre clé ne relit pas la
  chaîne.
- 8 tests neufs, vus rouges avant le code, puis trois mutations vues rouges (sans `ROLLBACK`, hash
  sans clé, clé non exigée). Suite complète : 444 verts, 4 sautés.
- `docs/contrats.md` § 2 : la clé, et la limite qui reste (effacer les dernières entrées passe
  encore, ancrage proposé à C). `demo/script.md` : la clé tirée une fois dans `~/.sas-cle-journal`.

## Pour tous
- **`SAS_CLE_JOURNAL` est désormais obligatoire** pour lancer le web ou le pipeline. Les tests la
  posent eux-mêmes (`tests/conftest.py`, bloc A) : rien à faire pour `pytest`.
- **Une base existante** (journal en sha256) apparaît « falsifiée » avec la nouvelle version : il
  faut repartir d'une base neuve. C'est le cas sur AWS, où l'infra est recréée à chaque séance.
- Le changement touche le contrat § 2 : relecture de B et de C demandée sur la PR.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| B | Relire la PR (contrat § 2) ; lancer le pipeline seul demande aussi `SAS_CLE_JOURNAL`. | fusion | ok |
| C | Relire la PR (contrat § 2) ; si un script de `infra/` lance la plateforme, y poser `SAS_CLE_JOURNAL` (tirée sur la plateforme, jamais dans Git). | fusion | ok |
