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
export SAS_ADMIN_MOTDEPASSE='<à choisir>'  # 12 caractères au moins ; ne sert qu'au premier lancement (base neuve)
# Clé HMAC du journal : tirée une fois, gardée hors de la base et hors de Git. Sans elle, la plateforme
# ne démarre pas ; avec une autre, le journal d'une base existante apparaît falsifié.
[ -f ~/.sas-cle-journal ] || (umask 077; openssl rand -hex 32 > ~/.sas-cle-journal)
export SAS_CLE_JOURNAL=$(cat ~/.sas-cle-journal)
export SAS_TRAITEMENT_INTERVALLE=10        # démo : on voit les états changer vite
export SAS_DELAI=120                       # démo : 2 minutes d'attente au lieu de 3 jours
export SAS_SANDBOX_ATTENTE=10              # démo : 10 s de battement après l'import (60 par défaut)
# Publication signée en TLS mutuel (C) ; sans SAS_PASSERELLE_URL, copie scp du M0.
export SAS_PASSERELLE_URL=https://10.42.2.10:8443 SAS_CLE_SIGNATURE=~/sas/signature.pem
export SAS_TLS_CA=~/sas/tls/ca.pem SAS_TLS_CERT=~/sas/tls/plateforme.pem SAS_TLS_CLE=~/sas/tls/plateforme.key
# LLM local (B) ; Ollama installé sur la plateforme par C. 7B retenu après mesure (point
# C-h10-aws : 18 s sur 1.1, 47 s sur 1.2, juste sur les deux ; le 3B fait une fausse alerte sur 1.1).
export SAS_MODELE=qwen2.5-coder:7b SAS_OLLAMA_URL=http://127.0.0.1:11434
# Source amont de démo (B) : le faux PyPI de demo/paquets/, qui sert demo-horodatage et relaie
# tout autre nom vers pypi.org (lecture seule). Sans SAS_PYPI_URL : le vrai PyPI.
.venv/bin/python demo/paquets/faux_pypi.py > ~/faux_pypi.log 2>&1 &   # 127.0.0.1:8081
export SAS_PYPI_URL=http://127.0.0.1:8081
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

## H10 — le MVP (la démo de 3 minutes ; atteint le 2026-10-10 : `docs/points/2026-10-10-C-h10-aws.md`)

### Ce qui doit être prêt avant

| Pièce | Qui | État au 2026-10-10 |
|---|---|---|
| Comptes, file d'attente, fiche, journal, décision humaine | A | sur `main` |
| Veille, délai, statique, sandbox → signaux, LLM, politique, `decision_humaine` | B | sur `main` |
| Faux PyPI de démo (`demo/paquets/faux_pypi.py`) : `demo-horodatage` 1.0 (ancienne), 1.1 (saine) et 1.2 (piégée), sorties à la demande | B | sur `main` |
| Publication signée en TLS mutuel, récepteur, `demo/forger.sh` | C | sur `main` |
| Sandbox v1 (Docker sans réseau, faux DNS qui enregistre, leurres) | C | branche `c/sandbox-v1`, pas encore en PR |
| Ollama + `qwen2.5-coder:7b` (et `:3b` en repli) sur la plateforme, temps de réponse mesuré | C | à faire |

### Avant de commencer (5 minutes avant)

1. Plateforme lancée (§ 3), faux PyPI compris, base neuve. Le faux PyPI vient d'être démarré :
   1.1 et 1.2 ne sont pas encore sorties.
2. « Demander un paquet » : `pypi`, `requests`, puis `pypi`, `demo-horodatage`. Attendre que
   `requests` (et ses dépendances) et `demo-horodatage` 1.0 soient `publiee`. `demo-horodatage`
   est alors au catalogue : la veille suit ses nouvelles versions.
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

**2. Une nouvelle version saine attend, puis passe (50 s)** — juste avant, dans le terminal
plateforme, la mise à jour saine sort, puis la version piégée 30 s plus tard (leurs attentes se
chevauchent, ce qui fait tenir la démo en 3 minutes) :

```bash
curl -X POST localhost:8081/demo/publier/demo-horodatage/1.1
sleep 30
curl -X POST localhost:8081/demo/publier/demo-horodatage/1.2
```

- « File d'attente » : `demo-horodatage` 1.1, puis 1.2, apparaissent avec leur compte à rebours
  de 2 minutes (au tour suivant de la veille, 10 s au plus).
  > « En vrai, 3 jours : la plupart des paquets piégés sont retirés par la communauté dans ce délai. »
- Pendant l'attente, ouvrir la fiche de `demo-horodatage` 1.0 (publiée : aucun signal,
  historique) et montrer « Autres versions ».
- À la fin du compte à rebours, 1.1 passe `en_analyse`, `approuvee`, puis `publiee`. Ouvrir sa
  fiche : « Aucun signal fort ni bloquant » ; l'historique montre la signature et la publication.
- Terminal serveur : `pip install -U demo-horodatage` installe la 1.1.

**3. Une version piégée est bloquée, avec ses preuves (60 s)** — 1.2 finit son attente 30 s après
la 1.1.

> « Le compte d'un mainteneur a été repris. La version 1.2 ajoute du code qui, dès l'import,
> lit les identifiants AWS et les envoie à un serveur de l'attaquant. »

- Elle passe `bloquee`. Ouvrir sa fiche, de haut en bas :
  - la phrase de la politique (« Bloquée : … ») et l'explication du LLM en français ;
  - la note « Décision prise par la politique (code). Le LLM explique et cite ; il ne peut ni
    approuver ni bloquer seul. » ;
  - les preuves, la plus grave d'abord :
    - statique : `exfiltration` (lecture de `~/.aws/credentials` **et** appel réseau au même
      point d'exécution, nouveau par rapport à 1.1), avec le fichier et la ligne ;
    - sandbox (v1 de C) : `lit_leurre` (le faux `~/.aws/credentials` lu) et `dns` vers
      `collecte.attaquant-demo.invalid` ;
    - `mainteneur_change` : aucun courriel en commun avec la 1.1 ;
  - la section Sandbox : la requête DNS vers le domaine de l'attaquant, le leurre lu.
  > « Elle n'a jamais touché le serveur. L'analyse a vu le code, la sandbox l'a vue lire un faux
  > secret et appeler son serveur. Le LLM explique, mais c'est le code qui décide. »
- Terminal serveur : `pip install demo-horodatage==1.2` échoue (introuvable sur la passerelle) ;
  `pip show demo-horodatage` affiche toujours 1.1.

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
| Pas de preuve de sandbox sur 1.2 | sa fiche : aucun signal `SANDBOX` | 1.2 reste bloquée par l'analyse statique (`exfiltration`) : montrer cette preuve ; ensuite, vérifier la sandbox v1 (`docker ps`) |
| La file reste vide | la veille n'a pas vu la nouvelle version | `curl localhost:8081/pypi/demo-horodatage/json` doit lister 1.1 / 1.2 ; sinon relancer le `curl -X POST …/demo/publier/…` ; voir `~/faux_pypi.log` et `SAS_PYPI_URL` |
| Le compte à rebours affiche une erreur | `SAS_DELAI` illisible | entier en secondes : `SAS_DELAI=120` |

### Vérifier le point H10 (`docs/roadmap.md`)

1. Une version propre attend son délai, est analysée, approuvée, signée et publiée, et le serveur
   l'installe : étape 2.
2. La version piégée est bloquée, avec les preuves statiques, les preuves de sandbox (DNS vers le
   domaine de l'attaquant, leurre lu) et une phrase en français : étape 3.
3. Une publication mal signée est refusée par la passerelle : étape 4.

Après la séance : `infra/aws/detruire.sh`.

## H16 — la démo complète (M2)

Le déroulé H10, plus ce que le M2 ajoute : le tableau de bord, le RAG cité par le LLM, la
révocation et l'inventaire, la décision humaine, et le relais d'API. On le répète une fois à trois
sur AWS, puis on gèle les fonctions (`docs/roadmap.md`). Consignes de C :
`docs/points/2026-10-11-C-h16-preparation.md`.

### Ce qui doit être prêt avant

| Pièce | Qui | État au 2026-10-11 |
|---|---|---|
| Révocation depuis la fiche, tableau de bord, page « Inventaire », correctifs A1 à A5 | A | sur `main` |
| RAG (16 473 documents dans `rag_index/`), veille RSS, sandbox v2 → signaux FORT, `decision_humaine` avec l'état attendu | B | sur `main` |
| Sandbox v2 (image `sas-sandbox:2`), relais d'API, sauvegardes, C1 à C7 | C | sur `main` |

### Préparer la plateforme (C, le jour même, environ 15 minutes)

1. Redéployer `main` (§ 2). L'index `rag_index/` n'est pas dans l'archive : il reste dans
   `~/sas-pme`, ne pas l'effacer.
2. Reconstruire l'image de la sandbox, pour qu'elle ait C1 et C2 :
   `docker rmi sas-sandbox:2`. Elle se reconstruit à la première analyse ; la lancer une fois avant
   la démo pour ne pas payer la construction pendant.
3. Lancer le web (§ 3) avec une **base neuve** (`SAS_DB` vers un fichier qui n'existe pas) et
   `SAS_SANDBOX_ATTENTE=10`.
4. **Relancer le faux PyPI** (port 8081) après le redéploiement, pour qu'il connaisse la 1.3. Ses
   versions vivent en mémoire : le relancer remet aussi 1.1, 1.2 et 1.3 « non sorties ». À faire
   avant de commencer, jamais pendant.
5. Vérifier l'index du RAG (1 s, sans Ollama ; attendu : `…/sas-pme/rag_index 16473 documents`) :
   `.venv/bin/python -I -c "from plateforme.pipeline.rag.index import Index, dossier; print(dossier().resolve(), Index(dossier(), None).compter(), 'documents')"`

### Avant de commencer (5 minutes avant)

Comme au H10 (requests et demo-horodatage 1.0 `publiee`, deux terminaux, navigateur sur
<http://localhost:8000> en `admin`). Ouvrir en plus les onglets « Tableau de bord » et
« Inventaire ». La préparation prend environ 7 minutes (mesuré par C : 98 s pour la 1.0, 330 s
pour requests et ses dépendances).

À la répétition à blanc de C, **certifi et idna sont passées « à revoir »** sur une seule alerte du
LLM (fausses alertes, signalées à B). Si c'est encore le cas, ne pas les trancher avant : elles
servent à l'étape 7.

### Minutage

Mesuré à la répétition à blanc de C (2026-10-11, 7B sur CPU, `SAS_DELAI=120`,
`SAS_SANDBOX_ATTENTE=10`) : la 1.1 est publiée 140 s après sa sortie ; la 1.2 est bloquée 72 s
après la fin de son délai ; **les étapes 2 et 3 prennent 252 s** depuis la sortie de la 1.1.

Pour la présentation de 3 minutes : sortir la 1.1, la 1.2 et la 1.3 **avant de prendre la
parole**, et commencer par les étapes 0 et 1 pendant que la plateforme travaille. Pour la vidéo :
couper les attentes au montage. Compter **8 à 10 minutes** pour la répétition complète.

| Étape | Durée |
|---|---|
| 0. Tableau de bord | 20 s |
| 1. Le serveur ne parle jamais à Internet, sauf aux API autorisées | 40 s |
| 2. Une version saine attend, puis passe | 140 s depuis sa sortie (120 s de délai) |
| 3. Une version piégée est bloquée, le LLM cite le RAG | 72 s après son délai (252 s pour 2 et 3) |
| 4. Révocation, puis l'alerte de l'inventaire | 60 s |
| 5. Une publication forgée est refusée | 30 s |
| 6. Le journal et le tableau de bord | 30 s |
| 7. Décision humaine sur la 1.3 « à revoir » | 40 s (plus le délai et l'analyse, en parallèle) |

### Déroulé

**0. Le tableau de bord (20 s)** — onglet « Tableau de bord » : les compteurs par état (requests,
ses dépendances et demo-horodatage 1.0 `publiee`, 0 bloquée ; certifi et idna peut-être « à
revoir ») et « Journal intact ».

> « La plateforme agréée : tout ce qui entre chez vous passe par ici, et tout y est tracé. »

**1. Le serveur ne parle jamais à Internet, sauf aux API autorisées (40 s)** — terminal serveur.
Le serveur a `HTTPS_PROXY=http://passerelle:3128` : un `curl` passe donc par le relais, qui refuse
tout ce qui n'est pas sur sa liste.

```bash
curl -m 5 --noproxy '*' https://pypi.org          # échoue : pas de route vers Internet
curl -s -o /dev/null -w '%{http_code}\n' -x http://passerelle:3128 https://api.github.com   # 200
curl -m 5 -x http://passerelle:3128 https://pypi.org   # refusé : CONNECT tunnel failed, response 403
pip install requests                               # marche : il vient de la passerelle
```

> « Ce serveur n'a aucun accès direct à Internet. Il parle à une API autorisée, ici GitHub, par un
> relais en liste fermée qui ne déchiffre rien. Tout le reste est refusé. Ses paquets viennent de la
> passerelle, qui ne reçoit que ce que la plateforme a vérifié et signé. »

**2. Une nouvelle version saine attend, puis passe** — comme l'étape 2 du H10 (1.1, puis 1.2
30 s plus tard, puis la 1.3 pour l'étape 7) :

```bash
curl -X POST localhost:8081/demo/publier/demo-horodatage/1.1
sleep 30
curl -X POST localhost:8081/demo/publier/demo-horodatage/1.2
sleep 30
curl -X POST localhost:8081/demo/publier/demo-horodatage/1.3
```
 Pendant l'attente, faire l'étape 1 si ce n'est pas déjà fait. À la fin, terminal
serveur : `pip install -U demo-horodatage` installe la 1.1.

**3. Une version piégée est bloquée, et le LLM cite ses sources (60 s)** — comme l'étape 3 du
H10, avec en plus, sur la fiche de la 1.2, sous l'explication du LLM : « Références : » et les
identifiants cités (au 2026-10-10 sur AWS : `CWE-522` et `T1552.005`).

> « Le LLM ne parle pas de mémoire : il s'appuie sur une base locale d'avis et de techniques
> d'attaque (OSV, GitHub, CWE, ATT&CK) et cite ce qu'il utilise. Il explique ; le code décide. »

**4. Révocation, puis l'alerte de l'inventaire (60 s)** — un avis tombe après coup sur la 1.1, déjà
installée sur le serveur.

> « Trois jours, une sandbox et un LLM ne voient pas tout. Quand un avis arrive après coup, on
> retire la version partout, et on sait où elle est déjà installée. »

- Fiche de demo-horodatage 1.1, section « Révocation » : raison « Avis publié après coup :
  mainteneur compromis. », puis « Révoquer ». La fiche passe `revoquee`, et l'historique garde la
  raison et l'admin.
- Onglet « Inventaire » (recharger) : la 1.1 est en tête, en rouge : « Révoquée depuis, et
  téléchargée N fois : un serveur l'a peut-être encore. »
- Terminal serveur : `pip download --no-deps -d /tmp/x demo-horodatage==1.1` échoue (retirée de la
  passerelle) ; `pip show demo-horodatage` montre qu'elle est encore installée : c'est ce que
  l'inventaire signale.

La 1.2, bloquée, n'a jamais été sur la passerelle : elle n'apparaît pas dans l'inventaire.

**5. Une publication forgée est refusée (30 s)** — comme l'étape 4 du H10 (`demo/forger.sh`).

**6. Le journal et le tableau de bord (30 s)** — « Journal », « Vérifier la chaîne » : chaîne
intègre. Puis « Tableau de bord » : 1 bloquée (1.2), 1 révoquée (1.1), « Journal intact ».

> « Chaque décision, de la machine comme des personnes, est chaînée et signée avec une clé qui
> n'est pas dans la base. Une ligne modifiée casse la chaîne, et on voit laquelle. »

**7. Décision humaine sur la 1.3 (40 s)** — la 1.3 (sortie à l'étape 2) arrive **« à revoir »** à
coup sûr : un seul signal FORT, `domaine_suspect`. Sa raison cite la ligne : « À revoir :
RAPPORT_URL = "https://horodatage-debug.ngrok-free.app/rapport" ». La fonction qui l'utilise n'est
jamais appelée à l'import : la sandbox ne voit rien.

> « Outil de debug oublié, ou porte de sortie ? La machine ne devine pas : elle demande à un
> humain. »

- « Tableau de bord », section « À trancher » : la 1.3 (et certifi, idna si elles y sont).
- Fiche de la 1.3 : raison « Tunnel ngrok vers l'extérieur, non justifié par le mainteneur. »,
  puis « Bloquer ». La preuve « admin : raison » s'ajoute et le journal la garde. Un second admin
  qui tranche la même version en même temps est refusé, pas écrasé.
- Si certifi et idna sont « à revoir » : les approuver avec une raison (« Alerte du LLM seule,
  rien en statique ni en sandbox. »). Une approbation ne lève jamais un signal bloquant.

### Si quelque chose casse pendant la démo (en plus du tableau H10)

| Symptôme | Où regarder | Repli |
|---|---|---|
| Pas de « Références » sous l'explication du LLM | `rag_index/` présent dans `~/sas-pme` ? | l'explication reste ; la décision ne dépend pas du RAG : le dire |
| La révocation affiche « Révocation échouée » (502) | le message de la passerelle sur la fiche | la version reste `publiee` : réessayer ; `curl -k https://10.42.2.10:8443/v1/health` |
| « Lecture de l'inventaire échouée » | `SAS_PASSERELLE_URL` et `SAS_TLS_*` exportées ? | montrer la fiche révoquée et `pip show` sur le serveur |
| Une page renvoie 403 « elle ne vient pas d'une page de cette origine » | l'adresse dans le navigateur | ouvrir l'interface par <http://localhost:8000> (le tunnel), pas par une autre adresse |
| Le `curl` vers `api.github.com` échoue | journal du relais sur la plateforme | `verifier_h3.sh` ; montrer le refus de `pypi.org`, qui est le message principal |
| Une analyse prend plus d'une minute de plus | `SAS_SANDBOX_ATTENTE` oubliée | relancer le web avec `SAS_SANDBOX_ATTENTE=10` |

### Vérifier le point H16 (`docs/roadmap.md`)

1. La démo H10 passe toujours (étapes 2, 3, 5).
2. Le M2 se voit : le RAG cité (étape 3), la révocation et l'inventaire (étape 4), le relais d'API
   (étape 1), le tableau de bord (étapes 0 et 6).
3. Chacun note ce qui casse et le temps de chaque étape, puis écrit son point H16. Ensuite, on gèle
   les fonctions.
