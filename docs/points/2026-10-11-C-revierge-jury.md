# Point C — site remis vierge avant le premier tour (12:38) — 2026-10-11

## Fait
Le site avait servi après la livraison de 11:05 (entre 11:15 et 11:24) : 9 versions, 7 paquets
installés sur le serveur, et un compte `jury` créé. **Remis vierge à 12:38**, tout archivé, rien
effacé :
- **Plateforme :** base archivée (`~/bases-archivees/sas-h16.db.20261011-103750`) ; web, faux PyPI
  et faux npm relancés sur une base vide ; journal intact.
- **Passerelle :** dépôts pip et npm, journaux d'accès et registre archivés dans
  `/var/lib/sas-archives/20261011-103812`, puis vidés. `/v1/inventory` répond `[]`. Le jeton
  Verdaccio et les nonces sont gardés.
- **Serveur :** `pip freeze` est vide et l'agent n'a aucune attente.
- **Comptes :** `admin` et `dev` ont leur mot de passe habituel. **`jury` est recréé en rôle admin,
  comme avant, avec le mot de passe déjà envoyé au jury** (connexion testée).
- **Ne plus rien demander sur le site avant le jury.**

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| — | Aucune | — | — |
