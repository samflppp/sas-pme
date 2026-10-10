# Point C (STEUSSO) — M1 : signature Ed25519 et récepteur de la passerelle — 2026-10-10

## Fait
- **`plateforme.signature.ed25519`** (plateforme) : la plateforme génère sa clé (fichier en 0600,
  refuse d'écraser une clé existante), signe un `Manifeste` (base64 des octets de
  `commun.canonique`) et construit le manifeste d'une publication (sha256 de chaque archive, nonce
  aléatoire, `emis_le` en UTC).
- **`passerelle.verification.verifier`** : applique les règles du contrat § 4. Il vérifie la
  signature avec la seule clé publique de la plateforme, refuse un manifeste de plus de 10 min (ou
  venu du futur), refuse un nonce déjà vu, et compare le hash de chaque archive (une archive en
  plus, en moins ou nommée avec un chemin est refusée). Un refus ne consomme pas le nonce.
- **`passerelle.recepteur`** (FastAPI) : `POST /v1/publish` (201, 400, 401, 409), `POST /v1/revoke`,
  `GET /v1/health`, `GET /v1/inventory` (vide pour l'instant). Les nonces survivent à un
  redémarrage. Une révocation ne retire que la version visée (`2.32.4` ne touche pas `2.32.40`).
- 28 tests, chaque règle cassée une fois pour voir son test au rouge. 139 tests passent sur la
  branche.

## Disponible pour vous
- Rien ne change pour vous : `signature.publier()` copie toujours par scp. Le passage au POST signé
  en TLS mutuel garde les mêmes signatures de fonctions.
- La démo H10, étape 3 (« publication forgée refusée »), est déjà couverte en test :
  `test_publication_forgee_refusee_et_rien_n_est_ecrit`.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| **A** | Pour la démo H10, étape 3 : préférez-vous un bouton caché « publication forgée » dans le web, ou un script `demo/forger.sh` que je lance depuis la plateforme ? | H10 | bouton ou script |

## Ensuite
- `publier()` / `revoquer()` en POST signé, en TLS mutuel (certificats générés à l'installation,
  hors Git). Installation du récepteur hors ligne sur la passerelle (`installer.sh`).
- Puis sandbox v1 et Ollama.
