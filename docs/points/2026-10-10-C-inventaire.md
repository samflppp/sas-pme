# Point C (STEUSSO) — inventaire de la passerelle et durcissement ufw — 2026-10-10

Reprise du poste de C (l'ancien est perdu). Clone neuf, `main` à jour, `pytest -q` au départ :
341 verts, 4 sautés (Docker, Ollama, POSIX). Les deux tâches « à finir le M1 » de C
(`docs/points/2026-10-10-A-m1-valide.md`) sont faites ici.

## Fait

### 1. Inventaire de la passerelle (`/v1/inventory`)
- **`passerelle/inventaire.py`** (nouveau) : lit le journal d'accès de pypiserver et agrège les
  téléchargements d'archives par `(nom, version)` en `EntreeInventaire` (contrat § 4). Pur,
  testable sans réseau.
  - On ne compte que les `GET /packages/<archive>` : la page d'index `/simple/` ne prouve pas une
    installation. `nom`/`version` déduits du **nom de fichier** d'archive (`packaging.utils`,
    wheel et sdist). `telechargements` = nombre de GET, `dernier` = date du plus récent.
- **`passerelle/recepteur.py`** : la route `/v1/inventory` lit `SAS_JOURNAL_ACCES` et renvoie la
  liste. Sans journal (ou route non branchée), elle renvoie `[]` comme avant.
- **`infra/passerelle/pypiserver.service`** : pypiserver écrit désormais le journal
  (`--log-file`, `--log-frmt`, `--log-req-frmt`).
- **18 tests** (7 inventaire + le test de route enrichi), chaque invariant cassé une fois pour le
  voir au rouge (filtre 2xx, compteur d'agrégation). 348 verts, 4 sautés.

### 2. Durcissement de la passerelle (`infra/aws/installer.sh`, étape 8)
- `ufw` : `default deny incoming`, puis **seulement** 22 et 8443 depuis la plateforme
  (`10.42.1.10`), 8080 et 4873 depuis le serveur (`10.42.2.20`). Tout le reste refusé.
- Les services tournaient déjà sous des comptes sans droits (`pypi`, `recepteur` : `--system`,
  `nologin`). Rien d'autre à changer de ce côté.
- **À vérifier sur AWS** (prochaine séance) : un port non prévu refusé, et `verifier_h3.sh`
  toujours 5 OK. Non testable en local (pas de passerelle Linux ici).

### 3. Correctif : répertoire d'état `/var/lib/sas` (bug trouvé en relecture)
- pypiserver écrit son journal dans `/var/lib/sas` sous `ProtectSystem=strict`. Les deux units
  (`pypiserver`, `recepteur`) déclaraient `StateDirectory=sas` **mais tournent sous des
  utilisateurs différents** (`pypi`, `recepteur`) : systemd réécrit le propriétaire du répertoire
  au démarrage de chaque service, donc le dernier démarré **cassait l'écriture de l'autre** (le
  journal n'aurait pas été écrit, ou les nonces). Sur AWS, le constat inventaire aurait échoué.
- Corrigé : `installer.sh` crée `/var/lib/sas` en `pypi:pypi` mode **2770** (setgid + group-write) ;
  le récepteur, membre du groupe `pypi`, y écrit ses nonces. Les deux units utilisent
  `ReadWritePaths=/var/lib/sas` au lieu de `StateDirectory=`, ce qui ouvre l'écriture sans
  réimposer de propriétaire.

### 4. Kit de validation AWS en une commande (`infra/aws/verifier_m1.sh`, nouveau)
- Jumeau de `verifier_h3.sh`. Enchaîne les 3 constats restants et sort un verdict `OK`/`KO` :
  1. inventaire : `pip install` depuis le serveur, puis `/v1/inventory` (TLS mutuel) liste le
     paquet et expose la machine ;
  2. durcissement : un port non prévu (9999, et 8443 depuis le serveur) refusé, le port légitime
     (8080 depuis le serveur) préservé, `ufw status` tracé, puis `verifier_h3.sh` → 5 OK ;
  3. `pytest -m "docker or ollama"` sur la plateforme (le script y pousse une archive du code).
- Objectif : la séance AWS devient « lancer `verifier_m1.sh`, coller la sortie dans ce point ».

## Disponible pour vous
- **A** : `GET /v1/inventory` renvoie `[{ecosysteme, nom, version, telechargements, dernier,
  machines}]`. Les 5 premiers champs suivent `EntreeInventaire` ; `machines` est en plus (voir
  « Demandes »). De quoi alimenter la **page inventaire** du M2.
- **B** : rien ne change pour toi.

## Format proposé (CLAUDE.md : le contrat ne fixe pas l'entrée, je propose)
- **Entrée** : le journal d'accès de pypiserver. Deux formes acceptées par le parseur :
  - ce que pypiserver écrit ici (date en tête via `--log-frmt`, pas de code HTTP) :
    `2026-10-11 09:00:01 10.42.2.20 - - "GET /packages/requests-2.32.4-...whl HTTP/1.1"` ;
  - le format access classique (`IP - - [date] "GET ..." 200`), au cas où on importe un journal.
  - Le code HTTP n'existe pas au log de requête (`before_request`) : on ne compte que les GET
    d'archives ; si un code est présent, on exige un 2xx.
- **Sortie** : `EntreeInventaire` (contrat § 4) + un champ `machines` hors contrat.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| A, B | `machine` (IP du serveur) **n'est pas** dans `EntreeInventaire` (contrat § 1). Choix retenu avec Sam : le laisser **hors contrat**, dans le JSON brut de la route (champ `machines`), sans PR `commun/`. OK pour vous, ou faut-il l'ajouter au contrat plus tard ? | M2 (page inventaire de A) | ok / ajouter au contrat |

## Réponses à vos demandes
- **(A, m1-valide : inventaire lu dans les journaux)** Fait, voir ci-dessus. Reste la vérif AWS
  après un vrai `pip install`.
- **(A, m1-valide : durcissement ufw)** Fait dans `installer.sh`. Reste la vérif AWS.

## Ensuite — séance AWS pour clore le M1 côté C (une commande)
Tout le code est fait et poussé ; il ne reste que les constats, qui exigent une infra vivante.
Les secrets de l'ancien poste sont perdus → l'infra repart de zéro. Marche à suivre :

```sh
cd infra/aws
aws configure                       # identifiants workshop (jamais dans Git) ; région us-east-1
cp config.env.exemple config.env    # puis régler MON_IP (curl -s https://checkip.amazonaws.com)
bash creer.sh                       # VPC public/privé, 3 instances, clé SSH, SG
bash installer.sh                   # pypiserver + récepteur signé + ufw + Ollama ; crée /var/lib/sas
bash verifier_m1.sh | tee /tmp/m1.txt   # les 3 constats d'un coup ; coller la sortie dans ce point
bash detruire.sh                    # NE PAS OUBLIER en fin de séance (~0,8 €/h sinon)
```

Attendu : `verifier_m1.sh` finit sur « M1 côté C : TOUS LES CONSTATS PASSENT ». Coller sa sortie
ici (sections 1 à 4) clôt le M1 côté C.

- **AWS nettoyé** : l'infra de la dernière séance (VPC `sas-pme` orphelin en us-east-1, 3 SG, 2
  subnets, IGW, key pair — toutes les instances étaient déjà `terminated`) a été détruite à la
  main (`etat.env` perdu, donc `detruire.sh` inutilisable). Compte propre, rien ne facture.
