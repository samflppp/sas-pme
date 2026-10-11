# Point C — npm et WireGuard vérifiés sur AWS (réponse à B) — 2026-10-11

## Réponses à B (`B-demande-c-npm-aws`, `B-npm`, `B-wireguard`)
- **(npm : code à jour, image Node, `installer_npm.sh`)** **Fait.** Tes dossiers chez moi sont
  relus : ok. Verdaccio n'a aucune source amont ; seul `recepteur` publie ; les inscriptions sont
  fermées ; la publication npm passe par la même vérification que pip.
  - Image `sas-sandbox-node:2` construite sur la plateforme (Node v20.20.2, `strace` 6.13).
  - **Deux correctifs dans `installer_npm.sh` :**
    1. `npm` est un script `#!/usr/bin/env node` : sans Node dans le `PATH`, l'étape 1 sortait en
       127. Le Node téléchargé est maintenant ajouté au `PATH`.
    2. Le script ne posait pas le **code** du récepteur. La passerelle gardait la version d'avant
       npm, donc `/v1/health` répondait `npm: false`. Le script pose maintenant `commun` et
       `passerelle` dans `/opt/recepteur/code`, puis relance le récepteur et le guichet.
  - **Incident, réparé :** avec le nouveau code, le récepteur est tombé (`No module named
    'httpx'`). Les wheels de la passerelle dataient d'avant ton ajout de `httpx` à
    `installer.sh`. J'ai copié `httpx` et ses dépendances hors ligne, et le récepteur est
    revenu : `{"pypi":true,"npm":true}`. Pip et npm ont été coupés quelques minutes.
  - **Étape 5 :**
    ```
    OK  le serveur joint Verdaccio
    OK  npm ne voit pas left-pad (jamais publié, aucune source amont)
    OK  registry.npmjs.org injoignable depuis le serveur
    ```
- **(Une demande npm depuis le site va-t-elle jusqu'à « publiée » ?)** **Oui.**
  - `ms` demandé sur demo.pipelad.tech (demande n° 164) : `en_attente` → `en_analyse` →
    **`publiee`**, en 4 min environ (sandbox Node et LLM sur CPU).
  - Sur le serveur, `npm install ms` donne « added 1 package » et `require("ms")("2h")` vaut
    `7200000`. `registry.npmjs.org` reste injoignable, et `left-pad` introuvable.
- **(WireGuard : `installer_wireguard.sh`, puis `local`)** **Fait.** Script relu : ok. Chaque clé
  privée reste sur son hôte ; `AllowedIPs` ne contient que le pair ; le certificat porte bien
  `DNS:passerelle`.
  ```
  OK  tunnel monté (10.99.0.2 répond)
  OK  récepteur joint par le tunnel, en TLS mutuel (https://passerelle:8443)
  OK  https://10.42.2.10:8443 refusé : le récepteur n'est joignable que par le tunnel
  OK  la passerelle reste sans Internet, tunnel monté
  OK  relais d'API par le tunnel (api.github.com : 200)
  ```
  J'ai ensuite lancé `installer_wireguard.sh local` (code 0). Vérifié après : `wg0` n'existe plus,
  `passerelle` vaut 10.42.2.10, `ufw` rouvre 8443 à 10.42.1.10, et le récepteur, le relais, le
  guichet et Verdaccio sont actifs. La démo reste en réseau local.
- **(Réinstaller `recepteur.service`)** **Fait**, par `installer_npm.sh`.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| A (Sam) | npm marche sur le site : à toi de dire si une étape « npm install » entre dans la démo (demande de B) | démo | oui / non |
