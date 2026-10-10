# Script de démo (A)

Deux parties : **lancer la plateforme** (commun à tous les points), puis le déroulé de chaque point
de rencontre. Le point H10 est **la démo minimale garantie** (`docs/roadmap.md`, M1).

## 1. Infra (C)

Depuis le poste de STEUSSO, voir `infra/README.md` : `creer.sh`, puis `installer.sh`. La région se
règle dans `infra/aws/config.env` (us-east-1 pour le compte du workshop) ; la plateforme est sur
CPU (`c7i.4xlarge`). `installer.sh` crée les certificats du lien, la clé de signature (sur la
plateforme) et le récepteur de la passerelle, puis affiche les variables `SAS_PASSERELLE_URL`,
`SAS_CLE_SIGNATURE` et `SAS_TLS_*` utilisées au § 3.

## 2. Déployer l'application sur la plateforme

Depuis la racine du dépôt, sur un poste qui a `infra/secrets/ssh_config` (celui de C) :

```bash
git archive --format=tar.gz -o /tmp/sas-pme.tar.gz main
scp -F infra/secrets/ssh_config /tmp/sas-pme.tar.gz sas-plateforme:
ssh -F infra/secrets/ssh_config sas-plateforme 'rm -rf ~/sas-pme && mkdir ~/sas-pme \
  && tar xzf sas-pme.tar.gz -C ~/sas-pme && cd ~/sas-pme \
  && python3 -m venv .venv && .venv/bin/pip install -q -e .'
```

`git archive` évite de mettre un accès au dépôt privé sur la machine.

## 3. Lancer le web (et donc `traiter()` en tâche de fond)

```bash
ssh -F infra/secrets/ssh_config sas-plateforme
cd ~/sas-pme
export SAS_DB=~/sas.db SAS_ARCHIVES=~/archives
export SAS_ADMIN_MOTDEPASSE='<à choisir>'  # ne sert qu'au premier lancement (base neuve)
export SAS_TRAITEMENT_INTERVALLE=10        # démo : on voit les états changer vite
export SAS_DELAI=120                       # démo : 2 minutes d'attente au lieu de 3 jours
# Publication signée en TLS mutuel (C) ; sans SAS_PASSERELLE_URL, copie scp du M0.
export SAS_PASSERELLE_URL=https://10.42.2.10:8443 SAS_CLE_SIGNATURE=~/sas/signature.pem
export SAS_TLS_CA=~/sas/tls/ca.pem SAS_TLS_CERT=~/sas/tls/plateforme.pem SAS_TLS_CLE=~/sas/tls/plateforme.key
# LLM local (B) ; Ollama installé sur la plateforme par C.
export SAS_MODELE=qwen2.5-coder:3b SAS_OLLAMA_URL=http://127.0.0.1:11434
# Source amont de démo (B, H10 seulement) : le faux PyPI de demo/paquets/. Sans, le vrai PyPI.
export SAS_PYPI_URL=<adresse du faux PyPI de démo>
.venv/bin/uvicorn plateforme.web.app:app --host 127.0.0.1 --port 8000
```

Le web n'écoute que sur la plateforme elle-même. On y accède par un tunnel SSH :

```bash
ssh -F infra/secrets/ssh_config -N -L 8000:127.0.0.1:8000 sas-plateforme
```

puis <http://localhost:8000> dans le navigateur. Se connecter (`admin`, le mot de passe choisi).
Les autres comptes se créent dans « Comptes » ; le mot de passe donné une fois est à changer à la
première connexion.

## H3 — preuve de vie (atteint le 2026-10-10, 5 OK sur 5 : `docs/points/2026-10-10-C-h3-ok.md`)

But (M0) : une personne demande `requests` dans le web ; la plateforme le télécharge, l'approuve et
le copie sur la passerelle ; sur le serveur, `pip install requests` marche alors que `curl
https://pypi.org` échoue. Se lance **sans** `SAS_PYPI_URL` (le vrai PyPI).

1. « Demander un paquet » : `pypi`, `requests`. Le catalogue montre `requests` et ses dépendances
   (`urllib3`, `idna`, `certifi`, `charset-normalizer`) `en_attente`.
2. Attendre un tour de `traiter()` : chacune passe `en_analyse`, `approuvee`, puis `publiee`. Une
   version qui reste `approuvee` a vu sa publication échouer : la raison est sur sa fiche, et elle
   est retentée au tour suivant.
3. Preuve sur le serveur : `infra/aws/verifier_h3.sh` (routes, `curl` qui échoue, `pip install
   requests` qui marche, `flask` introuvable).
4. `infra/aws/detruire.sh` après la séance.

`demander()` ne choisit que des versions publiées depuis plus que le délai réglé (`SAS_DELAI`) :
elles ne passent pas par la file d'attente. Une version qui **attend** arrive par la veille de B
(nouvelle version d'un paquet déjà au catalogue).

## H10 — le MVP (la démo de 3 minutes)

### Ce qui doit être prêt avant

| Pièce | Qui | État au 2026-10-10 |
|---|---|---|
| Comptes, file d'attente, fiche, journal, décision humaine | A | sur `main` |
| Veille, délai, statique, sandbox → signaux, LLM, politique, `decision_humaine` | B | sur `main` |
| Faux PyPI de démo (`demo/paquets/`) : `requests` et ses dépendances, une **nouvelle version saine** à « sortir » pendant la démo, la **version piégée** | B | à faire |
| Publication signée en TLS mutuel, récepteur, `demo/forger.sh` | C | sur `main` |
| Sandbox v1 (Docker sans réseau, faux DNS qui enregistre, leurres) | C | branche `c/sandbox-v1`, pas encore en PR |
| Ollama + `qwen2.5-coder:3b` sur la plateforme, temps de réponse mesuré | C | à faire |

### Avant de commencer (5 minutes avant)

1. Plateforme lancée (§ 3) avec `SAS_PYPI_URL` sur le faux PyPI, base neuve.
2. `requests` déjà demandé et `publiee` (étape H3) : il est au catalogue, donc la veille suit ses
   nouvelles versions.
3. Deux terminaux ouverts :
   - **serveur** : `ssh -F infra/secrets/ssh_config sas-serveur` ;
   - **plateforme** : `ssh -F infra/secrets/ssh_config sas-plateforme`, dans `~/sas-pme`.
4. Navigateur sur <http://localhost:8000>, connecté en `admin`, onglets « File d'attente » et
   « Journal » ouverts.
5. Répétition faite une fois sur la même infra : le LLM sur CPU peut prendre plusieurs dizaines de
   secondes par version, à intégrer au minutage.

### Déroulé

**1. Le serveur ne parle jamais à Internet (20 s)** — terminal serveur :

```bash
curl -m 5 https://pypi.org        # échoue : pas de route
pip install requests               # marche : il vient de la passerelle
```

> « Ce serveur n'a aucun accès à Internet. Il installe pourtant ses paquets : ils viennent de la
> passerelle, qui ne reçoit que ce que la plateforme a vérifié et signé. »

**2. Une nouvelle version saine attend, puis passe (50 s)** — juste avant, sortir la nouvelle
version saine de `requests` sur le faux PyPI (commande de B, `demo/paquets/`).

- « File d'attente » : la version apparaît avec son compte à rebours de 2 minutes.
  > « En vrai, 3 jours : la plupart des paquets piégés sont retirés par la communauté dans ce délai. »
- Pendant l'attente, ouvrir la fiche d'une version déjà publiée (preuves vides, historique).
- À la fin du compte à rebours : `en_analyse`, `approuvee`, puis `publiee`. Ouvrir sa fiche :
  « Aucun signal fort ni bloquant », l'historique montre la signature et la publication.
- Terminal serveur : `pip install -U requests` installe la nouvelle version.

**3. Une version piégée est bloquée, avec ses preuves (60 s)** — la version piégée de B est sortie
au début de l'étape 2 : son attente se termine en même temps, ou juste après.

- Elle passe `bloquee`. Ouvrir sa fiche, de haut en bas :
  - la phrase en français (« Bloquée : leurres lus : … ») et l'explication du LLM ;
  - la note « Décision prise par la politique (code). Le LLM explique et cite ; il ne peut ni
    approuver ni bloquer seul. » ;
  - les preuves, la plus grave d'abord : le leurre lu (sandbox), la ligne de `setup.py` qui lit un
    secret et appelle le réseau (statique), le domaine de l'attaquant ;
  - la sandbox : la requête DNS vers le domaine de l'attaquant, comptée (« ×6 »), le faux jeton lu.
  > « Elle n'a jamais touché le serveur. La sandbox l'a vue appeler son serveur et lire un faux
  > jeton. Le LLM explique, mais c'est le code qui décide. »
- Terminal serveur : `pip install <paquet piégé>` échoue (introuvable sur la passerelle).

**4. Une publication forgée est refusée (30 s)** — terminal plateforme :

```bash
demo/forger.sh            # requests 99.0.0, signé avec la clé de l'attaquant
```

Attendu : une ligne qui commence par `REFUSÉE par la passerelle : passerelle 401`, suivie du
motif donné par le récepteur.

> « Même quelqu'un qui a pris la plateforme et son lien réseau ne peut rien publier sans la clé de
> signature. » Terminal serveur : `pip install requests==99.0.0` échoue.

**5. Le journal prouve que rien n'a été modifié (20 s)** — « Journal », bouton « Vérifier la
chaîne » : « ✓ Chaîne intègre — N entrées vérifiées ».

> « Chaque décision, de la machine comme des personnes, est chaînée par hash. Une ligne modifiée
> casse la chaîne, et on voit laquelle. »

**Si une version passe « à revoir »** au lieu de « bloquée » ou « approuvée » : c'est la décision
humaine. Sur sa fiche, l'admin écrit une raison et clique « Approuver » ou « Bloquer » ; la preuve
« admin : raison » s'ajoute et le journal la garde. Une approbation ne lève jamais un signal
bloquant.

### Si quelque chose casse pendant la démo

| Symptôme | Où regarder | Repli |
|---|---|---|
| La version reste `approuvee` | sa fiche : raison de l'échec de publication | retentée au tour suivant (10 s) ; sinon `curl -k https://10.42.2.10:8443/v1/health` depuis la plateforme |
| Pas d'explication du LLM | journal : `llm_indisponible` ou `llm_hors_schema` | la décision reste celle du code : le dire, c'est le message de la démo |
| La version piégée n'est pas bloquée | sa fiche : signaux sandbox absents | vérifier que la sandbox v1 tourne (`docker ps`) ; montrer les preuves statiques |
| La file reste vide | la veille n'a pas vu la nouvelle version | vérifier `SAS_PYPI_URL` et que la version est bien « sortie » sur le faux PyPI |
| Le compte à rebours affiche une erreur | `SAS_DELAI` illisible | entier en secondes : `SAS_DELAI=120` |

### Vérifier le point H10 (`docs/roadmap.md`)

1. Une version propre attend son délai, est analysée, approuvée, signée et publiée, et le serveur
   l'installe : étape 2.
2. La version piégée est bloquée, avec les preuves statiques, les preuves de sandbox (DNS vers le
   domaine de l'attaquant, leurre lu) et une phrase en français : étape 3.
3. Une publication mal signée est refusée par la passerelle : étape 4.

Après la séance : `infra/aws/detruire.sh`.
