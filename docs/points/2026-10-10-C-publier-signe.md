# Point C (STEUSSO) — M1 : publication signée en TLS mutuel — 2026-10-10

## Fait
- **`signature.publier` / `revoquer` / `lire_inventaire` en POST signé** vers le récepteur, dès que
  `SAS_PASSERELLE_URL` est posée. Sinon, rien ne change : stub scp du M0. Un refus de la passerelle
  lève `signature.PublicationRefusee("passerelle 401 : …")`, que `traiter()` (B) écrit déjà comme
  raison et retente.
- **Installation** (`infra/aws/installer.sh`, étapes 6 à 8) :
  - certificats du lien (`certificats.sh`, hors Git) ;
  - clé de signature créée **sur** la plateforme ;
  - récepteur installé hors ligne sur la passerelle (service systemd, `10.42.2.10:8443`, certificat
    client exigé) ;
  - test de santé, et test qu'une connexion sans certificat client est refusée.
- **`demo/forger.sh`** (démo H10, étape 3, choix de A) : publication de `requests 99.0.0` signée avec
  une clé d'attaquant, qui reçoit « REFUSÉE par la passerelle : 401 signature invalide ».
- Testé en local de bout en bout (vrais certificats openssl, uvicorn en TLS mutuel, vraie clé) :
  publier, révoquer et forger.sh se comportent comme prévu. Corrigé au passage : Python 3.13+
  refuse une autorité sans `keyUsage`.
- 7 nouveaux tests (publier jusqu'au vrai récepteur), chacun cassé une fois. 225 tests passent.
- **Second H3 avec A** (comptes et `SAS_DELAI` sur `main`) : 5 OK sur 5, infra détruite.

## Disponible pour vous
- **A** : pour lancer le web en mode signé, ajouter aux variables :
  `SAS_PASSERELLE_URL=https://10.42.2.10:8443 SAS_CLE_SIGNATURE=~/sas/signature.pem
  SAS_TLS_CA=~/sas/tls/ca.pem SAS_TLS_CERT=~/sas/tls/plateforme.pem SAS_TLS_CLE=~/sas/tls/plateforme.key`.
  `installer.sh` les affiche à la fin. À mettre dans `demo/script.md` quand tu y repasses.
- `signature.PublicationRefusee` : à afficher sur la fiche si vous voulez distinguer un refus d'une
  panne réseau.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| A | `demo/script.md` : remplacer `SAS_PASSERELLE_SSH` et `SAS_PASSERELLE_CLE` par les variables ci-dessus, et ajouter l'étape `demo/forger.sh`. | H10 | ok |

## Ensuite
- Sandbox v1 (Docker sans réseau, faux DNS qui enregistre, leurres), puis Ollama sur la plateforme.
- Inventaire lu dans les journaux de pypiserver (pour `/v1/inventory`).
