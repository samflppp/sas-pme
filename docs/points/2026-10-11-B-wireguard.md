# Point B (Mouabd19) — WireGuard, mode « plateforme hors site » — 2026-10-11

Demande de Mouabd19 : WireGuard en plus du réseau local (extension n° 2 de la roadmap).
**J'ai touché aux dossiers de C** (`infra/`, `infra/passerelle/recepteur.service`) : c'est dit ici
(règle 2), tout est dans la PR de ce point.

## Fait
- **`infra/wireguard/rendre.py`** : la configuration `wg0` pour systemd-networkd, de la plateforme
  (`10.99.0.1`, écoute UDP 51820) et de la passerelle (`10.99.0.2`, appelle la plateforme).
  - AllowedIPs = le seul pair (`/32`) : la passerelle ne gagne **aucune route vers Internet**.
  - La clé publique du pair est vérifiée (32 octets en base64) : une ligne injectée est refusée.
- **`infra/aws/installer_wireguard.sh`** (après `installer.sh`) :
  - clés privées tirées **sur chaque hôte** par `openssl` (X25519, 0600), jamais copiées ; seules
    les publiques passent par le poste de l'opérateur ;
  - systemd-networkd porte le tunnel : **rien à installer sur la passerelle**, qui n'a pas Internet ;
  - groupes de sécurité : UDP 51820 de la passerelle vers la plateforme seulement ;
  - le récepteur n'écoute plus que sur `10.99.0.2` et ufw n'ouvre 8443 qu'à `10.99.0.1` par `wg0` ;
  - relais d'API par le tunnel (`10.99.0.1:3129`) ;
  - sur la plateforme, `passerelle` = `10.99.0.2` : le certificat (`DNS:passerelle`) reste valable ;
  - vérifications : tunnel monté, récepteur joint en TLS mutuel par le tunnel, **chemin direct
    `10.42.2.10:8443` refusé**, passerelle toujours sans Internet, relais d'API qui marche ;
  - `installer_wireguard.sh local` revient au réseau local en une commande.
- **`recepteur.service`** : l'adresse d'écoute devient `SAS_RECEPTEUR_HOTE` (défaut `10.42.2.10`,
  inchangé) ; le mode tunnel la change par un fichier `wireguard.conf` de systemd.

## Vérifié
- 15 tests (`tests/infra/test_wireguard.py`), dont la clé tirée par `openssl` comparée à celle que
  dérive WireGuard (X25519). Suite complète : 730 verts, 6 sautés.
- Code cassé une fois : AllowedIPs ouvert à `0.0.0.0/0`, clé non vérifiée, récepteur figé sur
  `10.42.2.10` → les tests tombent au rouge.

## Limites
- **Pas monté pour de vrai** : mon conteneur n'a ni module WireGuard ni AWS.
- En mode tunnel, `verifier_h3.sh` et `verifier_m1.sh` visent encore `10.42.2.10:8443` : les
  lancer après `installer_wireguard.sh local`.
- La démo reste en réseau local (décision H16) ; le tunnel est une preuve à part.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Relire `infra/` ; lancer `infra/aws/installer_wireguard.sh` sur AWS, coller les 5 « OK » de l'étape 6, puis `installer_wireguard.sh local` | WireGuard vérifié | la sortie |
| C (STEUSSO) | Réinstaller `recepteur.service` (`installer.sh` ou `installer_npm.sh`) : l'adresse d'écoute est maintenant une variable, même valeur par défaut | rien | ok |
| A (Sam) | Rien à coder ; une ligne « mode hors site par WireGuard » dans le deck si tu veux | deck | oui / non |
