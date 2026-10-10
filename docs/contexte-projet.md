# sas-pme — contexte complet du projet

Ce document permet à une personne, ou à un agent (Kiro, Claude Code), qui arrive sur le projet de tout
comprendre sans rien redemander. Il dit ce qu'on construit, pour qui, pourquoi on l'a construit ainsi,
ce qui a été décidé et écarté, qui fait quoi, et comment on travaille.

Dernière mise à jour : 10 octobre 2026, à la fin du cadrage (T0 poussé sur `main`).

---

## 1. Le hackathon

- **Track 3 « Open Track : Uncharted Frontiers ».** Seule règle : IA × cybersécurité, côté défense.
  Le sujet cite les PME, la chaîne d'approvisionnement logicielle, les infrastructures critiques et la
  conformité continue.
- **Nos axes du sujet :** n° 2, surveillance continue de la chaîne d'approvisionnement logicielle et IA,
  et n° 4, défendre les PME qui n'ont ni équipe cyber ni budget.
- **Grille du jury :**

  | Critère | Poids |
  |---|---|
  | Importance et originalité du problème | 25 % |
  | Efficacité défensive **démontrée**, avec preuves et métriques | 25 % |
  | Impact et passage à l'échelle | 20 % |
  | Viabilité économique (« pensez clients dès le premier jour ») | 20 % |
  | Pitch et démo | 10 % |

- **Livrables :**
  - un dépôt de code ;
  - une vidéo de démo ;
  - un pitch deck, avec une diapositive « why this problem » (chiffres, incidents) et une diapositive
    « what's next » (premiers clients, feuille de route à 6 mois) ;
  - une fiche de défense ;
  - un PoC qui marche sur un scénario défensif concret.
- **Consignes des organisateurs :**
  - énoncer le problème en une phrase et dire quel défenseur on aide ;
  - vérifier qu'on ne relève pas de la Track 1 ou 2 (point d'étape avec les mentors à 18 h 30).
- **Soutiens présents :** Bpifrance, ESSEC Alumni, Kryptosphère, GitGuardian (chaîne
  d'approvisionnement, secrets), Utopia (mentors IA), AWS (crédits).
- **Temps :** 34 heures depuis la fin du cadrage. Équipe de trois.

## 2. Le problème et le pitch

**Phrase-problème.** Les PME et startups qui développent installent chaque jour des paquets PyPI que
personne ne relit. La chaîne d'approvisionnement logicielle est pourtant devenue un vecteur d'attaque
majeur (ultralytics en décembre 2024, typosquats, mainteneurs compromis), et ces entreprises n'ont ni
RSSI ni SOC.

**Pitch en une phrase.** Un sas de sécurité posé dans la PME retient chaque nouvelle version de paquet
Python le temps qu'une IA locale l'examine et lise ce qu'Internet en dit, puis il surveille les
connexions sortantes. Si un paquet piégé passe quand même, le sas le démasque dès qu'il appelle son
serveur.

**Accroche.** « Le sas qui fait attendre les mises à jour, pas vos développeurs. »

**Sens du mot.** « Sas » veut dire **sas de sécurité** : une zone d'attente entre deux portes. Ce n'est
pas un SaaS, et le produit tourne en local. À l'oral, éviter la confusion ; un nom de produit est encore
à choisir (pistes : Écluse, Airlock).

**Postulat de départ du porteur.** La meilleure protection d'une PME est de raisonner en local : un
intermédiaire posé chez elle entre Internet et son réseau, qui vérifie automatiquement, avec l'aide de
l'IA, ce qui entre (les mises à jour) et ce qui sort (les requêtes).

## 3. Le client idéal

- **Profil :** startup ou PME tech française de **20 à 80 personnes**, dont **5 à 25 développeurs
  Python** (data, IA, FastAPI/Django). Elle vend à des clients régulés (hôpitaux, banques, assureurs,
  secteur public) qui lui envoient des questionnaires de sécurité. Elle n'a pas de RSSI : c'est le CTO
  qui porte la sécurité.
- **Secteurs :** healthtech, fintech et assurtech, legaltech, SaaS B2B vendu aux grands comptes.
- **Pressions :** DORA par ricochet (via leurs clients financiers), NIS2 comme fournisseur, CRA s'ils
  vendent un logiciel, ISO 27001, SOC 2 ou HDS en cours.
- **Déclencheurs d'achat :**
  - un questionnaire de sécurité d'un grand compte ;
  - un audit qui approche ;
  - un incident dans l'actualité ;
  - une due diligence de levée de fonds.
- **Qui achète, qui utilise :**
  - le décideur est le CTO ;
  - l'utilisateur est le lead dev ou le DevOps ;
  - les prescripteurs sont l'infogérant, le cabinet d'audit ISO et l'assureur cyber.
- **Prix (hypothèse) :** 300 à 800 € par mois selon le nombre de développeurs.
- **Exemple fictif :** Medlytics, Lyon, 45 personnes, 14 développeurs Python, données de santé (HDS),
  clients CHU. La CTO a reçu un questionnaire de 120 questions, dont 15 sur la chaîne logicielle.
- **Ne sont pas clients :**
  - les PME qui ne développent pas (option écartée, voir § 6) ;
  - les grandes entreprises, qui ont un SOC, Artifactory ou Sonatype ;
  - les équipes de moins de 5 développeurs ;
  - les équipes 100 % JavaScript, tant que npm n'est pas couvert.
- **Questions de qualification :**
  1. Combien de développeurs écrivent du Python ?
  2. Un client vous a-t-il interrogé sur vos dépendances ?
  3. Qui valide l'ajout d'un paquet ?
  4. ISO 27001, SOC 2 ou HDS en cours ?
  5. Avez-vous le droit d'envoyer du code ou des données à un service cloud tiers ?

**À vérifier avant le deck :** les dates réglementaires (DORA, calendrier du CRA) et les ordres de
grandeur viennent de mémoire, pas d'une source relue. Le meilleur test reste d'appeler 3 à 5 CTO de ce
profil pendant le hackathon.

## 4. Ce que fait le produit

Cinq barrières, chacune détaillée dans `.kiro/specs/sas-pme/design.md`.

1. **Index PyPI filtré.** Le sas se présente comme un index PyPI : une ligne `PIP_INDEX_URL` suffit, sans
   déchiffrement TLS. `pip` ne voit que les versions approuvées. Une version nouvelle est cachée et part
   en quarantaine. `pip` prend la précédente sans erreur ni attente.
2. **Quarantaine active (48 h par défaut), avec analyse du paquet :**
   - étage 1, des contrôles déterministes : typosquat, âge, changement de mainteneur, OSV, OpenSSF
     malicious-packages, statut yanked, sdist seul ;
   - étage 2, le diff avec la version précédente : code exécuté à l'installation, `exec`/`base64`,
     secrets lus, domaines en dur, blocs de haute entropie ;
   - étage 3, un LLM local qui produit un verdict JSON et une phrase en français.
3. **Veille sur Internet pendant la quarantaine (toutes les 2 h) :**
   - sources structurées : OSV, statut PyPI, OpenSSF ;
   - sources libres : blogs de chercheurs, lus par le LLM local ;
   - seuls le nom du paquet et la version sortent.
4. **Surveillance des sorties :**
   - un proxy CONNECT sans déchiffrement relève le domaine, le port, les octets et la durée de chaque
     connexion ;
   - signaux : domaine nouveau, domaine jeune (RDAP), IP brute, battement régulier ;
   - **corrélation** : un domaine nouveau contacté par un poste moins de 10 min après une installation
     bloque le domaine et la version, pour toute la PME ;
   - un agent LLM résume les signaux par poste ;
   - les serveurs de CI sont en liste fermée.
5. **Console et journal :**
   - une phrase en français et ses preuves pour chaque décision ;
   - approuver ou bloquer en un clic ;
   - un journal append-only chaîné par hash, qui sert de preuve pour NIS2 et le CRA.

**Voie rapide :** une version qui corrige une CVE critique et ne lève aucun signal aux étages 1 et 2
passe sans attendre le délai.

**Adoption initiale :** un paquet jamais vu reçoit d'office sa version la plus récente publiée depuis
plus de 48 h, si elle est propre aux étages 1 et 2. Sinon, `pip` échouerait.

## 5. Principes non négociables

| Principe | Conséquence dans le code |
|---|---|
| **Le code décide, l'IA alerte et explique** | un signal `llm` ou `watch` peut monter un risque, jamais l'abaisser ni approuver ; vérifié par un test d'invariant (A2) |
| **Un texte lu n'est jamais une instruction** | code de paquet, changelog, article : encadrés `<donnee>`, sortie JSON validée par schéma, réponse hors schéma ignorée |
| **Un article ne débloque jamais** | une source libre met seulement « à revoir » ; seule une source structurée bloque automatiquement |
| **Tout local** | LLM sur le boîtier (Ollama) ; aucun service cloud managé (ni Bedrock, ni Lambda, ni DynamoDB) |
| **On lit Internet, on ne lui parle pas de vous** | ne sortent que nom + version (OSV, PyPI), des domaines (RDAP), des lectures de flux publics |
| **Transparent pour le développeur** | le chemin de `pip` n'attend jamais le LLM ni la veille |
| **Fail-closed** | amont injoignable : on sert le cache approuvé, on refuse le neuf |
| **Le journal ne s'efface pas** | aucune méthode `update`/`delete` sur la table `journal` |

## 6. Les décisions prises, et pourquoi

Chaque ligne a été tranchée par le porteur pendant le cadrage. La rouvrir demande une raison nouvelle.

| Décision | Options écartées | Pourquoi |
|---|---|---|
| Cible : **PME et startups qui développent** | PME qui ne développent pas (winget, Chocolatey, via infogérant) | corpus d'attaques réelles publics, démo plus nette ; le porteur l'a choisie en connaissant la concurrence (Socket, Sonatype) |
| **Tout local** pour le LLM | API Claude ; hybride | cohérence avec le postulat ; données de santé et financières chez le client idéal |
| **PyPI** seul pour le PoC | npm ; les deux | terrain Python de l'équipe ; outillage natif ; « les deux » doublait la plomberie |
| **Index PyPI + proxy CONNECT sans déchiffrement** | proxy avec interception TLS | pas d'autorité de certification à déployer, pas de casse du pinning ; l'interception était l'attaque la plus forte de la revue |
| **Quarantaine active = cacher + délai + veille** | analyse synchrone ; délai seul | pip n'attend jamais ; la lenteur du LLM local devient invisible ; le délai donne le temps de lire ce que le monde découvre |
| **Agent des sorties** sur les métadonnées de connexion | relecture du code de la PME ; second avis LLM | rattrape ce que la première barrière laisse passer ; la corrélation paquet ↔ domaine est le point original |
| **AWS : une EC2 GPU joue le boîtier** | tout sur un PC ; services managés | un PC sans GPU met 30 à 60 s par verdict ; l'EC2 reste « un boîtier local » dans le récit, sans service managé |
| **Un seul dépôt, deux branches** | trois dépôts | un seul programme ; `models.py` partagé ; le jury clone un seul dépôt |
| **Branche partagée** pour A et B | une sous-branche chacun | fichiers bien séparés ; moins d'étapes |

## 7. La revue critique du cadrage

Avant le design, l'idée de départ a été attaquée par trois outils.

- **Trois personas (sécurité, architecte, produit).** Les trois convergent :
  - se limiter aux mises à jour et aux paquets, sans couvrir « tout le trafic sortant » ;
  - le code déterministe décide et l'IA lit et explique ;
  - pas de reprise de Windows Update (déjà signé, déjà géré par WSUS) ;
  - la liste fermée des sorties est la réponse aux mises à jour signées et piégées (SolarWinds, 3CX).
- **Premortem.** Cinq causes d'échec, dans l'ordre :
  1. une démo où une règle simple fait aussi bien que l'IA ;
  2. un week-end mangé par la plomberie proxy/TLS ;
  3. des infogérants qui refusent de retarder les patchs ;
  4. un classement en Track 2 par le jury ;
  5. une injection de prompt qui fait approuver un paquet en pleine démo.

  La cause à surveiller en premier est la n° 1, car elle porte sur le critère à 25 %.
- **Avocat du diable.** Verdict **STOP** sur la formulation d'origine (« l'IA approuve automatiquement,
  intégration transparente, tout le trafic »), probabilité d'erreur 75 %. L'attaque principale :
  SolarWinds, 3CX et xz arrivaient signés, donc un vérificateur IA ne voit rien, et un boîtier qui
  déchiffre tout devient la cible n° 1.

  **Ce qui a changé ensuite :**
  - l'IA ne peut plus approuver ;
  - plus de déchiffrement TLS ;
  - le périmètre est resserré sur PyPI ;
  - la corrélation des sorties a été ajoutée ;
  - une mesure chiffrée est exigée.

  **Deux questions restent ouvertes :** la colonne LLM bat-elle la colonne déterministe ? Les clients
  paieront-ils ?

## 8. Concurrence et créneau

| Acteur | Ce qu'il fait | Ce qu'il ne fait pas |
|---|---|---|
| Pare-feu avec filtrage web (Fortinet, Stormshield) | réputation d'URL | juger une version de paquet |
| SASE (Zscaler, Cloudflare Gateway) | filtrage des sorties, DLP | lire un diff de paquet ; tout local |
| Socket.dev, Phylum (Veracode), Sonatype Firewall, Artifactory/Nexus | analyse de paquets, pour les grandes équipes de dev | vendre à une PME sans IT ; corréler avec les sorties réseau ; tout local |
| Délai d'attente de `uv` ou Renovate | attendre quelques jours | analyser, lire la veille, expliquer, surveiller les sorties |

**Notre créneau :** tout local, pour une PME sans équipe sécurité, avec les deux barrières reliées.
Le paquet est retenu à l'entrée, et s'il passe, sa connexion sortante le trahit.

## 9. Architecture technique

Détail complet : `docs/architecture.md`. Spec : `.kiro/specs/sas-pme/`.

- **Le boîtier, une EC2 `g4dn.xlarge` (GPU T4) en démo :**
  - Ubuntu 22.04 avec l'AMI Deep Learning ;
  - Python 3.12, FastAPI et uvicorn (index et console sur le port 8080) ;
  - le proxy CONNECT `asyncio` (port 3128) ;
  - Ollama avec `qwen2.5-coder:7b`, sur `127.0.0.1:11434` ;
  - SQLite ;
  - pypiserver de démo, sur `127.0.0.1:8081`.
- **Configuration d'un poste :**
  - `pip config set global.index-url http://<sas>:8080/simple` ;
  - `HTTPS_PROXY=http://<sas>:3128`.
- **Repli si le quota GPU AWS vaut 0 :** `c7i.4xlarge` (CPU) avec `qwen2.5-coder:3b`.

**Modules et propriétaires :**

| Module | Propriétaire | Rôle |
|---|---|---|
| `sas/models.py` | A (T0) | contrats partagés : `State`, `Level`, `Source`, `Signal`, `Finding`, `Flow`, `HumanDecision` |
| `sas/config.py` | commun | réglages `SAS_*`, un bloc par personne |
| `sas/store.py`, `sas/journal.py` | A | SQLite, journal chaîné |
| `sas/policy.py` | A | fonction pure qui donne l'état d'une version |
| `sas/upstream.py`, `sas/index.py` | A | client amont PEP 691, index filtré PEP 503 |
| `sas/pipeline.py`, `sas/app.py` | A | orchestration, minuteries, assemblage |
| `sas/console/` | A | console FastAPI + Jinja2 + HTMX |
| `sas/checks.py`, `sas/diffscan.py` | B | étages 1 et 2 |
| `sas/llm.py` | B | client Ollama confiné |
| `sas/watch.py` | B | veille |
| `sas/egress_agent.py` | B | résumés LLM des sorties |
| `measure/`, `corpus/` | B | mesure de la détection |
| `sas/proxy.py`, `sas/egress.py` | C | proxy CONNECT, signaux de sortie, corrélation |
| `infra/` | C | EC2, systemd, scripts des postes, durcissement |

## 10. L'équipe et la répartition

| Qui | Rôle | Branche | Tâches |
|---|---|---|---|
| **A — Sam** (`samflppp`, porteur) | plateforme : contrats, données, décision, index, orchestration, console, deck | `pipeline-plateforme` | T0 (fait), A1 à A6 |
| **B — Mouabd19** | agentique IA : analyse, LLM, veille, agent des sorties, mesure, paquets de démo | `pipeline-plateforme` | B0 à B7 |
| **C — STEUSSO** (spécialiste réseau) | infra et réseau : EC2, Ollama, proxy, corrélation, réseau de démo, postes, durcissement, vidéo | `infra-reseau` | C0 à C6 |

Le détail de chaque tâche (fichiers, signatures, tests) est dans `.kiro/specs/sas-pme/tasks.md`. La
roadmap visuelle est dans `docs/roadmap.pdf`.

## 11. Planning et points de synchronisation

H0 = fin du cadrage. Chaque point de synchronisation dure 15 min et réunit les trois personnes.

| Heure | Ce qui doit marcher | Si non |
|---|---|---|
| **H1** | `models.py` sur `main` (**fait**) ; EC2 lancée ou quota GPU demandé ; phrase-problème envoyée | — |
| **H6** | `pip install` depuis un PC passe par l'index du sas sur l'EC2 ; première fusion `infra-reseau` → `main` | C aide A sur l'index |
| **H13** | mesure (configuration 1) de bout en bout ; le proxy relaie ; le LLM répond en moins de 5 s ; fusion des deux branches | **on coupe la veille** ; modèle 3b si lent |
| **H17** | démo complète répétée une fois | on gèle les fonctions |
| **H22** | deck, mesure finale, vidéo enregistrée | la vidéo passe avant le deck |
| **H24–H33** | marge, sommeil en quinconce, répétitions | — |

## 12. Comment on travaille avec Git

- **Dépôt :** https://github.com/samflppp/sas-pme, privé. Trois branches : `main`,
  `pipeline-plateforme` (A et B) et `infra-reseau` (C).
- **Installation :**
  1. `git clone https://github.com/samflppp/sas-pme.git` ;
  2. `cd sas-pme && python -m venv .venv && .venv\Scripts\activate && pip install -e ".[dev]"` ;
  3. `git switch <ma-branche>`.

  Il faut Python 3.12 au minimum.
- **Routine sur une branche partagée, plusieurs fois par heure :**
  1. `git pull --rebase` ;
  2. un petit commit ;
  3. `pytest` ;
  4. `git pull --rebase && git push`.
- **Aux points de synchronisation :**
  1. ouvrir une Pull Request de chaque branche vers `main` et la fusionner ;
  2. dans chaque branche, faire `git merge main`.
- **Fichiers communs :**
  - `sas/models.py` ne se modifie qu'aux points de synchronisation, sur `main` ;
  - une dépendance tardive dans `pyproject.toml` s'ajoute sur `main` ;
  - `sas/store.py` appartient à A, et C code contre ses signatures ;
  - `config.py` et `tests/conftest.py` : chacun ajoute dans son bloc ;
  - `app.py` : seul A le modifie.
- **On ne coche pas les cases de `tasks.md`**, car c'est une source de conflits. L'avancement se suit
  sur un tableau GitHub Project, s'il est créé.
- **Méthode de test :** test qui échoue, code minimal, test vert, puis **casser une fois** le code
  regardé pour vérifier que le test tombe au rouge.

## 13. La démo (3 minutes)

1. `pip install` d'un paquet courant à travers le sas : rien de visible. *Transparent.*
2. Une version piégée sort : `pip` ne la voit pas, et la console explique pourquoi en français. *Le
   code a lu ce que personne ne lit.*
3. Un faux article « cette version est sûre » ne débloque rien. *L'IA ne peut qu'alerter.*
4. Un développeur force l'installation. En moins d'une minute, le domaine et le paquet sont reliés et
   bloqués. *La deuxième barrière tient.*
5. Diapositive de mesure : taux de détection et de fausses alertes, en trois colonnes (étage 1 seul ;
   étages 1 à 3 ; avec la veille), sur environ 80 versions.

## 14. Risques ouverts

| Risque | Parade |
|---|---|
| Quota GPU AWS à 0 | demande dès H0 ; repli CPU avec un modèle 3b |
| « Où est l'IA ? » si le LLM ne bat pas les règles | mesure dès H13 ; mettre en avant l'écart changelog/code et la lecture des articles |
| Plomberie qui mange le temps | un seul écosystème, pas de déchiffrement TLS |
| Injection de prompt en démo | le LLM ne peut que monter un risque ; test dédié (B3) |
| Classement en Track 2 | insister : PME sans SOC, sorties corrélées, tout local, ce n'est pas un scanner de dépendances |
| Le boîtier compromis | durcissement (C5), journal chaîné, diapositive dédiée |
| Échantillons malveillants du corpus | ne jamais les installer ni les exécuter ; Python en `-I`, dossier à part |

## 15. Hors périmètre du PoC (diapositive « what's next »)

- npm, winget, mises à jour d'OS ;
- comparaison de l'archive au tag git (le piège xz) ;
- bac à sable d'exécution ;
- second LLM relecteur ;
- signaux d'envoi anormal, de noms générés, d'heures anormales ;
- multi-sites et console d'infogérant à plusieurs clients ;
- authentification de la console ;
- haute disponibilité ;
- télémétrie partagée entre parcs (une version libérée après avoir été vue saine sur N parcs).

**Feuille de route à 6 mois (proposition) :**
- **Mois 1–2 :** pilote avec 3 clients du profil idéal.
- **Mois 3–4 :** npm et PyPI pour la CI ; console d'infogérant.
- **Mois 5–6 :** partenariat avec un assureur cyber ; pré-amorçage Bpifrance.

## 16. Où trouver quoi

| Quoi | Où |
|---|---|
| Ce contexte | `docs/contexte-projet.md` |
| Produit et principes (lus par Kiro) | `.kiro/steering/product.md` |
| Pile et règles techniques (lus par Kiro) | `.kiro/steering/tech.md` |
| Exigences au format EARS | `.kiro/specs/sas-pme/requirements.md` |
| Design (modules, données, politique, LLM, erreurs, tests) | `.kiro/specs/sas-pme/design.md` |
| Plan d'implémentation par personne | `.kiro/specs/sas-pme/tasks.md` |
| Machines, logiciels, flux de données | `docs/architecture.md` |
| Roadmap visuelle | `docs/roadmap.pdf` (source `docs/roadmap.html`) |
| Sujet du hackathon | page Notion « Track 3 — Open Track: Uncharted Frontiers » |

## 17. Glossaire

- **Sas** : la zone d'attente de sécurité, c'est-à-dire notre boîtier. Ce n'est pas un SaaS.
- **Quarantaine** : la période pendant laquelle une version est cachée à `pip` et examinée.
- **Signal** : un indice levé par une source (`checks`, `diff`, `llm`, `watch`, `egress`), avec un
  niveau `info`, `medium`, `strong` ou `block`.
- **Politique** : la fonction déterministe qui transforme les signaux en état de version.
- **Veille** : la lecture périodique de ce qu'Internet dit d'une version.
- **Battement** : des connexions régulières vers un même domaine, signe d'un logiciel qui attend des
  ordres.
- **Corrélation** : le lien entre un paquet installé et un domaine nouveau contacté juste après par le
  même poste.
- **Voie rapide** : le passage sans délai d'un correctif de CVE critique propre.
- **Adoption initiale** : l'approbation d'office d'une version ancienne et propre, pour un paquet
  jamais vu.
