# Point A (Sam) — correctifs A3 et A4 de la relecture de B — 2026-10-10

## Fait
- **Une seule transaction par écriture** (`Base._ecriture`) : chaque méthode qui écrit prend le verrou
  d'écriture du fichier (`BEGIN IMMEDIATE`) avant de lire le dernier hash, écrit sa donnée et son
  entrée de journal, puis valide. Toute erreur annule l'ensemble. La connexion attend 30 s une autre
  écriture au lieu de lever « database is locked ».
- **A3 : deux `Base` sur le même fichier ne cassent plus la chaîne.** Test : deux connexions, deux
  fils, 300 entrées ; la chaîne cassait à l'entrée 36 avant le correctif, elle est intacte après.
- **A4 : `changer_etat(..., attendu=None)`.** Avec `attendu`, la mise à jour ne passe que si la
  version est encore dans cet état ; sinon `ValueError` (« n'est plus a_revoir : elle est
  bloquee »), sans rien écrire, journal compris. Sans `attendu`, rien ne change pour les appels
  existants. Le changement d'état et son journal partent ensemble : si le journal échoue, l'état
  revient.
- **Révocation (web)** : passe `attendu=Etat.PUBLIEE`. Si l'état a changé pendant l'appel à la
  passerelle, la fiche le dit (409), et `revocation_concurrente` est journalisé.
- 6 tests neufs, vus rouges avant le code, puis mutations vues rouges (`BEGIN` au lieu de
  `BEGIN IMMEDIATE`, condition d'état retirée, `COMMIT` au lieu de `ROLLBACK`). Suite complète :
  455 verts, 7 sautés.
- `docs/contrats.md` § 2 : la nouvelle signature de `changer_etat`.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| B | Dans `decision_humaine`, passer `attendu=Etat.A_REVOIR` à `changer_etat` : deux décisions simultanées seront refusées au lieu de s'écraser. La page web dit déjà le `ValueError` sur la fiche (400). | A4 complet | ok |
