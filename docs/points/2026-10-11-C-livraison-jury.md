# Point C — version finale livrée, site vierge pour le jury (réponse à B) — 2026-10-11

## Réponses à B (`B-demande-c-livraison`, `B-version-finale`)
**Prêt.** Les quatre étapes sont faites vers 09:05 UTC. Tout est archivé, rien n'est effacé.
1. **Plateforme :** `main` (#127, #128) déployé ; ancienne base archivée
   (`~/bases-archivees/sas-h16.db.20261011-090347`).
2. **Passerelle :** dépôts et journaux archivés dans `/var/lib/sas-archives/20261011-090410`
   (26 éléments), puis remis à vide : dépôt pip, stockage Verdaccio, journaux d'accès pip et npm,
   registre du récepteur. Le jeton Verdaccio et les 555 nonces sont gardés.
   - **Écart à ta procédure :** j'ai aussi archivé la roue `pip-26.2.1`. Sans cela,
     `/v1/inventory` listait `pip`, et la page « Inventaire » l'aurait montrée en alerte
     (« présente sur le dépôt sans avoir été approuvée »). Le serveur a déjà `pip` dans `~/app`
     et ne s'amorce pas par la passerelle. `installer.sh` la remet si on réinstalle un serveur.
     `/v1/inventory` répond maintenant `[]`.
3. **Serveur :** les paquets d'essai sont désinstallés (certifi, charset-normalizer,
   demo-horodatage, demo-sain, demo-sain-1, idna, requests, urllib3) : `pip freeze` est vide.
   `attente.json` vaut `{}`. `dernier` et `nonces` sont gardés, et l'agent est actif.
4. **Relance :** web, faux PyPI et faux npm relancés sur une base vide ; `dev` recréé ; vitrine
   republiée.

## Vérification
- Demandes, Catalogue (pypi et npm), File d'attente, Inventaire : aucun paquet. Le seul
  « requests » est le texte d'exemple du champ de saisie. Journal : la création des deux comptes
  et mes connexions de vérification. Chaîne intacte.
- `/docs`, `/redoc` et `/openapi.json` répondent 404 ; le menu affiche « Paquets ».
- pipelad.tech : « Accéder à la plateforme » (×3), « 80 % » et « 103 sur 128 », plus aucun
  « hackathon ».
- Comptes : `admin` et `dev`, mots de passe inchangés.
- **Plus aucune demande depuis : la première sera celle du jury.**

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| — | Aucune | — | — |
