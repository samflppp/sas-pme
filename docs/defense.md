# Fiche de défense

Pour le jury, et pour nous trois avant les questions. Chaque affirmation renvoie à sa preuve : une
commande de la démo, un fichier du dépôt, une mesure ou une source publique (§ 9). Ce qui n'est pas
prouvé est dit comme tel (§ 6). État au 2026-10-11 : M2 clos, fonctions gelées.

## 1. En une phrase

Une **plateforme agréée**, seule machine de la PME reliée à Internet, attend 3 jours chaque nouvelle
version de paquet, l'analyse sur place (code, sandbox, IA locale), puis la publie, **signée**, dans
une **passerelle sans Internet** où les serveurs sensibles s'approvisionnent.

> « Vos serveurs n'installent que ce qu'on a vérifié. »

**Le problème, avec deux cas réels :**
- **ultralytics (PyPI, décembre 2024)** : la version 8.3.41, publiée le 4 décembre, installe un
  mineur de cryptomonnaie. La 8.3.42, publiée le lendemain **pour corriger**, contient le même code
  malveillant. Le 7 décembre, la 8.3.45 et la 8.3.46 arrivent piégées à leur tour, publiées avec un
  jeton volé lors de la première intrusion (ReversingLabs, Wiz).
- **Shai-Hulud (npm, septembre 2025)** : un ver qui compromet plus de 500 paquets. Il vole les
  jetons GitHub et les clés AWS, GCP et Azure, puis se republie dans d'autres paquets. La CISA
  recommande de s'en tenir aux versions publiées **avant le 16 septembre 2025** (alerte du
  23 septembre 2025).

La consigne de la CISA est, après coup, exactement notre délai. Nous l'appliquons d'avance, à chaque
version.

## 2. Ce que la démo prouve, et comment

| Affirmation | Preuve | Où |
|---|---|---|
| Le serveur sensible n'a pas Internet | `curl --noproxy '*' https://pypi.org` échoue ; aucune route dans le sous-réseau privé, DNS du VPC coupé | démo, étape 1 ; `infra/aws/verifier_h3.sh` (6 contrôles) |
| Il installe pourtant ses paquets | `pip install requests` marche, depuis la passerelle | démo, étape 1 |
| Il ne reçoit que ce qui a été publié | `pip install flask` : introuvable (pypiserver sans repli vers pypi.org) | `verifier_h3.sh` |
| Une version saine passe, après son délai | 1.1 : en attente, analysée, approuvée, signée, publiée ; `pip install -U` | démo, étape 2 |
| Une version piégée est bloquée, avec ses preuves | 1.2 : statique (`exfiltration`, `__init__.py:23`), sandbox (DNS de l'attaquant, faux `~/.aws/credentials` lu), explication du LLM qui cite ses sources (CWE-522, T1552.005 à la répétition) | démo, étape 3 ; répétition AWS de C |
| Le doute va à un humain, pas à la machine | 1.3 : un seul signal FORT (tunnel ngrok jamais appelé) : « à revoir » ; l'admin tranche avec une raison ; une seconde décision simultanée est refusée | démo, étape 7 |
| Une publication forgée est refusée | `demo/forger.sh` : `passerelle 401 : signature invalide` | démo, étape 5 |
| Un avis tombé après coup se traite | révocation depuis la fiche, archives retirées de la passerelle ; `/inventaire` signale « révoquée depuis, et téléchargée N fois » | démo, étape 4 |
| Les API sortantes sont contrôlées | depuis le serveur : `api.github.com` 200, `pypi.org` 403 (relais en liste fermée, sans déchiffrement) | démo, étape 1 |
| Root sur la plateforme ne donne ni le serveur, ni Internet | 8 contrôles sur AWS, chacun avec sa contre-épreuve : SSH refusé vers le serveur et la passerelle avec chaque clé de la plateforme, pypiserver injoignable, aucune route vers `1.1.1.1`, relais hors liste 403, autre clé de signature 401 | `infra/aws/verifier_compromission.sh` ; `demo/reseau.md` § 3 |
| Le journal n'est pas réécrit en silence | « Vérifier la chaîne » : intègre ; une entrée modifiée casse la chaîne à son numéro | démo, étape 6 ; `tests/plateforme/test_journal_hmac.py` |

Le code est testé : **551 tests verts** (2026-10-11). Chaque test neuf a été
vu rouge avant le code, puis le code a été cassé exprès (mutations) pour vérifier qu'un test tombe.

## 3. Les chiffres

**Mesure finale au 2026-10-11** (`mesure/resultats.md`, `python3 -I mesure/mesurer.py`). Même
corpus pour les trois lignes : 128 versions malveillantes (Datadog) et 98 saines (PyPI, dont 48
paquets peu connus qui n'ont servi à régler aucune règle). Chaque ligne ajoute une couche du
pipeline à la précédente. Une version est arrêtée si un contrôle lève un signal FORT ou BLOQUANT.

| Contrôles | Détection (malveillantes arrêtées) | Fausses alertes (saines arrêtées) |
|---|---|---|
| 1. Contrôles seuls (nom + code) | 93 / 128 (73 %) | 0 / 98 (0 %) |
| 2. + sandbox | **103 / 128 (80 %)** | **0 / 98 (0 %)** |
| 3. + LLM/RAG | 103 / 128 (80 %) | 0 / 98 (0 %) |

La ligne 2 rejoue la vraie sandbox (60 s de battement, leurres, `strace`, réseau interne) ; ses
226 rapports sont gardés dans `mesure/rapports_sandbox/`. La ligne 3 a été lancée sur la plateforme
AWS, avec le vrai LLM et le RAG. Pour comparaison, le nom seul (typosquat) n'arrête que 1 version
malveillante sur 30 du corpus OpenSSF (3 %, mesure du 2026-10-10).

> « 80 % des versions malveillantes arrêtées, 0 fausse alerte sur 98 versions saines. La détection
> vient de règles et d'une sandbox qu'on peut vérifier ; l'IA explique, elle ne décide pas. »

**Ce que disent les chiffres, honnêtement :**
- **La sandbox paie :** 10 détections de plus, sans fausse alerte. Elle voit ce que le code cache :
  un DNS vers l'attaquant (`bytedance-chat` → `0wn.sh`), le sondage du cloud et de Kubernetes
  (`169.254.169.254`), une commande lancée, `/etc/passwd` lu.
- **Le LLM n'ajoute aucune détection, et c'est voulu.** Dans le produit, il analyse **chaque**
  version : il lit les constats, le rapport de la sandbox et les cas proches du RAG, puis il donne
  son avis (des signaux, au plus FORT), une explication en français et ses références (CWE,
  ATT&CK, cas connus). Mais le code garde la décision : son signal FORT ne compte que s'il
  s'appuie sur le paquet et qu'un autre contrôle a relevé au moins un doute. Sur ce corpus, son
  avis ne pouvait donc changer le verdict que de 5 versions sur 226 (les seules interrogées par la
  mesure, pour ne pas payer le LLM là où rien ne peut changer) : il n'en change aucun, et ne crée
  aucune fausse alerte. Sa valeur se voit sur la fiche de chaque version : l'explication qu'un CTO
  sans équipe sécurité peut lire.
- **La réponse au premortem** (« une règle simple fait-elle aussi bien que l'IA ? »,
  `contexte.md` § 8) : pour **détecter**, oui, et nous l'assumons, c'est ce qui rend le verdict
  fiable et vérifiable. Pour **expliquer** à un CTO sans équipe sécurité, il faut le LLM.
- **Les 25 manquées** comptent ultralytics 8.3.41, 8.3.42 et 8.3.46 (la 8.3.45 est arrêtée :
  `domaine_suspect`). La sandbox installe sans les dépendances, comme le produit : une charge qui
  part à l'import d'un paquet qui ne s'importe pas seul n'est pas vue. C'est le rôle du délai de
  3 jours et de la veille, qui l'auraient vue retirée.
- Le délai ne se mesure pas sur ce corpus : il dépend de la vitesse de retrait de chaque version.
- Autres limites de la mesure : `mesure/resultats.md` § Limites (campagnes en série, groupe
  « populaires » optimiste, cibles Windows).

**Le LLM sur de vrais paquets** (vérifié sur AWS par C, 2026-10-11, `mesure/llm_paquet.py`) :
certifi 2026.7.22, idna 3.20 et requests 2.34.2, sains, sont **approuvés** ; la 1.2 piégée garde
ses signaux FORT et cite ses sources. Ces trois paquets avaient d'abord déclenché de fausses
alertes : la règle du § 4 les a supprimées.

## 4. Les questions probables, et nos réponses

### Le problème et l'originalité (25 %)

**« Artifactory, Nexus, Sonatype Firewall ou Socket le font déjà. »**
Ils sont vendus à des équipes de développement outillées, avec un SOC derrière. Notre client n'a ni
RSSI ni SOC : un CTO porte la sécurité. Ce qu'on fait de différent :
- tout est **local**, IA comprise : rien de son code ni de ses dépendances ne part dans un cloud ;
- le **cloisonnement se démontre** : le serveur n'a pas de route vers Internet, ce n'est pas une
  règle de proxy ;
- le **verdict est expliqué en français**, avec ses preuves, à quelqu'un qui n'est pas analyste.

**« Pourquoi 3 jours ? »**
Parce que la communauté trouve vite, mais pas tout de suite.
- **ultralytics :** la 8.3.41 (4 décembre 2024) est repérée dès le lendemain, quand une version
  propre (8.3.43) sort. Un délai de 3 jours l'aurait tenue à l'écart, ainsi que la 8.3.42.
- **Shai-Hulud :** la CISA recommande de revenir aux versions d'avant le 16 septembre 2025, une
  semaine avant son alerte. C'est un délai, imposé après coup.

Pendant l'attente, la veille lit les avis (OSV) et les flux de chercheurs. Le délai se règle
(`SAS_DELAI`).

**« Et un correctif de sécurité urgent ? 3 jours, c'est long. »**
- **Un correctif d'urgence peut être piégé lui-même.** Le cas est réel : la 8.3.42 d'ultralytics,
  publiée le 5 décembre 2024 pour corriger la version piégée de la veille, contenait le même code
  malveillant. Un mainteneur compromis a aussi intérêt à écrire « correctif de sécurité, mettez à
  jour tout de suite ». Si l'étiquette « urgent » suffisait à sauter le délai, le délai ne
  protégerait plus.
- **L'analyse ne prend pas de retard.** La version urgente passe la statique, la sandbox et le LLM
  pendant son attente : on sait tôt si elle est saine. Le serveur garde entre-temps sa version
  actuelle, qui marche.
- **Le cloisonnement réduit le risque de l'attente, il ne l'annule pas.** Le serveur n'a pas de
  sortie vers Internet : une faille exploitée pendant ces 3 jours peut difficilement exfiltrer des
  données ou télécharger une seconde charge. Il ne bloque pas une attaque entrante : ne pas dire que
  le serveur est intouchable.
- **La sortie de secours, prévue juste après le hackathon : une voie d'urgence tracée.** Un admin lève
  le délai d'**une** version, avec une raison écrite. L'analyse complète tourne quand même (statique,
  sandbox, LLM, politique, signature) : une version piégée reste bloquée. Le geste est inscrit au
  journal (qui, quand, pourquoi), pour l'auditeur.
- **Aujourd'hui :** le délai se règle (`SAS_DELAI`), mais pour toutes les versions à la fois ; la levée
  version par version n'existe pas encore (§ 6). Le dire si le jury insiste.

> « Le correctif d'urgence d'ultralytics était lui-même piégé : l'urgence est le meilleur
> déguisement. Pour une vraie urgence, un admin lève le délai d'une seule version, avec sa raison ;
> l'analyse complète tourne quand même, et le geste est signé au journal. On saute l'attente, jamais
> la vérification. »

À ne pas avancer : un chiffre sur le temps que met une PME à appliquer un correctif ; aucun n'est
vérifié.

### L'efficacité défensive (25 %)

**« Une IA qui lit du code se trompe, ou se fait manipuler. »**
D'où la règle centrale : **le code décide, l'IA alerte et explique.**
- Une politique déterministe décide (`plateforme/pipeline/politique.py`) : un signal BLOQUANT
  bloque, un signal FORT met « à revoir », sinon la version est approuvée.
- Le LLM ne peut lever qu'un signal FORT au plus : jamais approuver, jamais bloquer, jamais abaisser
  un autre signal. Les types le refusent (`commun/modeles.py`).
- **Le LLM ne crée jamais seul un doute.** Son signal FORT redescend à MOYEN s'il ne s'appuie pas
  sur ce que le paquet a montré (une ligne, un domaine, un élément de la sandbox), **ou** s'il n'est
  pas accompagné d'un constat d'au moins MOYEN hors du LLM (statique, sandbox ou veille). Il aggrave
  un doute réel ; il n'en invente pas. Ces règles viennent de fausses alertes vues sur certifi, idna
  et requests pendant les répétitions (`plateforme/pipeline/llm.py`, points B du 2026-10-11).
- Le code du paquet, les changelogs, les articles et le RAG sont passés au LLM comme **données**,
  entre balises ; sa sortie est validée par un schéma, et une réponse hors schéma est ignorée.

**« SolarWinds, 3CX ou xz arrivaient signés par leur éditeur. »**
C'est vrai, et une signature d'éditeur ne prouve pas qu'une version est saine. On ne s'appuie pas
dessus. On ajoute :
- le **délai**, qui laisse le temps à la communauté de trouver ;
- la **sandbox**, qui observe le comportement (fichiers lus, DNS, connexions, processus) au lieu de
  lire seulement le code ;
- le **cloisonnement** : même une version piégée installée ne peut pas joindre Internet depuis le
  serveur.

Une porte dérobée dormante et bien cachée, comme xz, peut passer les trois : le dire.

**« Un paquet peut détecter la sandbox, ou attendre avant d'agir. »**
Oui. La sandbox v2 observe 60 s après l'import et suit aussi le code natif (`strace`). Une analyse
sabotée (traces effacées, journal tronqué) met la version « à revoir », jamais « approuvée ». Une
bombe à retardement plus longue que l'observation reste possible : le cloisonnement réseau limite
alors ce qu'elle peut faire. Et une version qui ne s'importe pas sans ses dépendances n'est observée
qu'à l'installation (ultralytics) : c'est alors au délai et à la veille de la prendre.

**« Et si la plateforme est compromise ? »**
Réponse détaillée de C : `demo/reseau.md` § 3, schéma `demo/schema-reseau.svg`.
- Une plateforme **usurpée** ne publie rien : il lui faut le certificat du lien **et** la clé de
  signature (étape 5 de la démo).
- Une plateforme **réellement prise** (root) peut signer une version piégée avec la vraie clé,
  élargir la liste du relais d'API et réécrire sa propre base.
- Elle ne peut pas joindre le serveur ni la passerelle en SSH, ni donner Internet aux serveurs, ni
  lire leurs données : **prouvé sur AWS par 8 contrôles** (`infra/aws/verifier_compromission.sh`).
  La passerelle garde son propre registre de ce qui a été publié et quand.
- Ensuite : la clé de signature quitte la plateforme (YubiKey ou HSM, avec un geste humain), une
  double signature (code + admin), l'ancre du journal sur la passerelle, une liste du relais signée.

> « Prendre la plateforme ne donne ni Internet aux serveurs, ni leurs données. Le pire possible est
> une publication signée, et la clé de signature quitte la plateforme dans la version suivante. »

**« Le journal peut-il être effacé ? »**
Il est en ajout seul, chaîné par un HMAC-SHA256 dont la clé n'est pas dans la base. Modifier,
insérer ou recalculer une entrée sans la clé est détecté. **Limite :** effacer les dernières entrées
ne casse pas la chaîne. L'ancrage de la fin du journal sur la passerelle est convenu avec C pour
après le hackathon (`docs/contrats.md` § 2).

### L'impact (20 %)

**« Qui est le client ? »**
Une startup ou PME tech de 20 à 80 personnes, avec 5 à 25 développeurs Python ou JavaScript. Elle vend
à des clients régulés (santé, finance, assurance, secteur public) qui lui envoient des
questionnaires de sécurité, et elle n'a pas de RSSI (`contexte.md` § 4).

**« Qu'est-ce que ça change pour lui ? »**
Il répond à la question « comment contrôlez-vous vos dépendances logicielles ? » avec une preuve :
un journal intègre de chaque version entrée, de qui l'a décidée et pourquoi. Et quand un avis tombe
trop tard, l'inventaire dit quels serveurs ont la version.

### La viabilité économique (20 %)

**« Combien, et qui paie ? »**
Hypothèse à tester : **300 à 800 € par mois**. Le CTO décide ; le lead dev ou le DevOps utilise ;
l'infogérant, l'auditeur ISO et l'assureur cyber prescrivent. Les déclencheurs d'achat sont un
questionnaire d'un grand compte, un audit, un incident dans l'actualité ou une due diligence de
levée de fonds.

**« Les pressions réglementaires ? »** Détail et sources : § 8. En bref :
- **NIS2** : les entités assujetties doivent sécuriser leur chaîne d'approvisionnement et tenir
  compte des pratiques de leurs fournisseurs directs (art. 21). Notre client est souvent sous le
  seuil ou hors des secteurs visés ; il est touché **par ricochet**, par les questionnaires et les
  contrats de ses clients.
- **DORA** s'applique depuis le 17 janvier 2025 aux entités financières, avec des exigences sur
  leurs prestataires TIC (art. 28 à 30). Une startup qui vend à une banque ou un assureur en reçoit
  les clauses et les audits.
- **Le Cyber Resilience Act** : le signalement des vulnérabilités activement exploitées s'applique
  depuis le 11 septembre 2026, le reste le 11 décembre 2027. Il exige notamment d'identifier et de
  documenter les composants d'un produit (annexe I, partie II).

> « On ne vend pas la conformité. On donne la preuve que les clients de nos clients demandent sur
> leurs fournisseurs : ce qui entre, qui l'a décidé, pourquoi, et où c'est installé. »

**« Et le matériel ? »**
Le LLM tourne sur CPU : 50 à 60 s par version (7B, mesuré sur AWS). Les versions arrivent au fil
de l'eau et attendent 3 jours : ce temps ne gêne personne. Pas de GPU nécessaire.

## 5. Les choix qu'on assume

| Choix | Ce qu'on a écarté | Pourquoi |
|---|---|---|
| L'IA n'approuve jamais | une IA qui laisse passer | une erreur d'IA ne peut qu'alerter, pas ouvrir la porte |
| L'IA ne crée pas seule un doute | un LLM qui met « à revoir » sur sa seule lecture | il aggrave un constat réel ; sinon chaque `requests.get` deviendrait une alerte |
| Pas de déchiffrement TLS | un boîtier qui inspecte tout le trafic | il deviendrait la cible n° 1 ; le relais d'API ne voit que le nom du site |
| La plateforme pousse, la passerelle ne tire rien | une passerelle qui va chercher | une passerelle compromise ne peut rien tirer d'Internet |
| Signature Ed25519 de chaque publication | la confiance dans le seul lien chiffré | une plateforme usurpée ne publie pas |
| Tout local (LLM, RAG, sandbox) | une IA dans le cloud | rien du client ne sort ; seuls des noms de paquets et des versions partent vers Internet |

## 6. Les limites, dites avant qu'on nous les montre

- **pip seulement.** npm (Verdaccio sans source amont) est conçu mais pas construit : coupé de la
  démo le 2026-10-11. Le parcours est le même ; seul le dépôt de la passerelle change.
- **Pas de WireGuard.** La démo est sur un réseau local (AWS) ; le mode hors site vient ensuite.
- **Pas de voie d'urgence** pour un correctif critique : le délai se règle pour toutes les versions
  à la fois, pas pour une seule (§ 4).
- **Fin du journal non ancrée** : effacer les dernières entrées n'est pas détecté (§ 4).
- **Une plateforme réellement prise peut signer** : clé matérielle dans la version suivante.
- **Pas de SBOM.** L'inventaire dit quelles versions les serveurs ont installées, mais il ne produit
  pas de SBOM au format CycloneDX ou SPDX : un export est sur la feuille de route.
- **Interface de démo publique** (`demo.pipelad.tech`, derrière Caddy en HTTPS) : connexion
  obligatoire et contrôle d'origine des POST actifs, mais pas encore de limite au nombre d'essais de
  connexion, ni de drapeau `Secure` sur le cookie de session. Comptes de démo en rôle `dev`, mots de
  passe longs.
- **La sandbox installe sans les dépendances** : elle n'a pu observer l'import que de 58 des
  98 versions saines, et 12 des 25 malveillantes manquées ont échoué à l'import (dont ultralytics).
  Idée notée, pas codée : installer dans la sandbox les dépendances depuis le dépôt des versions
  déjà approuvées.
- **Mesure sur corpus**, pas en production. Les chiffres valent pour ces corpus, à leur date.
- **Le LLM sur CPU est lent** (50 à 60 s par version) : sans effet sur un délai de 3 jours, visible
  en démo (attentes coupées au montage de la vidéo, jamais simulées).
- **La plateforme d'intégration n'existe pas** (installation en une commande, configuration de pip
  sur les serveurs, appliance) : c'est la priorité n° 1 après le hackathon.

## 7. Ensuite (6 mois)

1. La plateforme d'intégration : installation en une commande, pip et npm configurés sur les
   serveurs, image d'appliance.
2. npm, puis images Docker, Maven et NuGet.
3. La clé de signature hors de la plateforme, et une double signature (code + admin).
4. L'ancrage du journal sur la passerelle ; une voie d'urgence tracée ; un export SBOM de
   l'inventaire ; la sandbox avec les dépendances déjà approuvées (elle verrait ultralytics).
5. Une console multi-clients pour les infogérants, et une télémétrie partagée entre clients (une
   version libérée après avoir été vue saine ailleurs).

Premiers clients visés : des startups qui reçoivent des questionnaires de sécurité de grands
comptes, par leurs infogérants et leurs auditeurs ISO.

## 8. Réglementation : ce qui est vérifié

Vérifié le 2026-10-11 sur les sources du § 9. Ce n'est pas un avis juridique : le droit applicable
à un client dépend de son secteur, de sa taille et du droit national.

| Texte | Ce qu'il dit, pour nous | Dates |
|---|---|---|
| **NIS2**, directive (UE) 2022/2555 | Art. 21(2)(d) : « sécurité de la chaîne d'approvisionnement », y compris les relations avec les fournisseurs directs. Art. 21(2)(e) : sécurité de l'acquisition, du développement et de la maintenance, traitement et divulgation des vulnérabilités. Art. 21(3) : tenir compte des vulnérabilités propres à chaque fournisseur direct et de la qualité de ses produits et de ses pratiques, y compris son développement sécurisé. S'applique aux entités moyennes et grandes (en général à partir de 50 salariés ou 10 M€ de chiffre d'affaires) des secteurs listés | transposition due le 17 octobre 2024 |
| **NIS2 en France** | Transposée par le projet de loi « résilience des infrastructures critiques et renforcement de la cybersécurité », voté au Sénat. Le 6 octobre 2026, son examen à l'Assemblée a été retiré de l'ordre du jour, sans nouvelle date : **les obligations NIS2 ne s'appliquent pas encore en droit français**. La Commission a saisi la Cour de justice de l'UE contre la France (avec l'Irlande, l'Espagne et les Pays-Bas) le 8 juillet 2026 | état au 6 octobre 2026 |
| **DORA**, règlement (UE) 2022/2554 | Entités financières. Art. 28 à 30 : gestion du risque lié aux prestataires TIC tiers ; art. 30 : clauses minimales des contrats, renforcées (accès, audit, sortie) pour les fonctions critiques ou importantes | applicable depuis le 17 janvier 2025 |
| **Cyber Resilience Act**, règlement (UE) 2024/2847 | Produits comportant des éléments numériques. Annexe I, partie II, point 1 : identifier et documenter les vulnérabilités et les composants, notamment par un SBOM couvrant au moins les dépendances de premier niveau. Signalement des vulnérabilités activement exploitées et des incidents graves. Un SaaS pur est en général lu comme hors champ (service, pas produit) ; un agent, une CLI ou une application installée y entrent | en vigueur le 10 décembre 2024 ; signalement depuis le 11 septembre 2026 ; obligations principales le 11 décembre 2027 |

**Ce qu'on peut dire, et ce qu'on ne dit pas :**
- **À dire :** la plateforme fournit des preuves pour les mesures sur la chaîne d'approvisionnement
  (délai, analyse, signature, journal intègre, décisions motivées) et un inventaire des versions
  installées, utile quand une vulnérabilité tombe.
- **À ne pas dire :** « conforme NIS2 », « conforme CRA », « remplace un SBOM ». Aucun outil ne rend
  conforme seul, et nous ne produisons pas de SBOM.
- **À ne pas dire non plus :** « NIS2 s'impose à toutes les PME françaises ». Ce n'est vrai ni par
  la taille, ni aujourd'hui en droit français.

## 9. Sources

Consultées le 2026-10-11.

**Incidents**
- ReversingLabs, « Compromised ultralytics PyPI package delivers crypto coinminer » :
  <https://www.reversinglabs.com/blog/compromised-ultralytics-pypi-package-delivers-crypto-coinminer>
- Wiz, « Ultralytics AI Library Hacked via GitHub for Cryptomining » :
  <https://wiz.io/blog/ultralytics-ai-library-hacked-via-github-for-cryptomining>
- CISA, « Widespread Supply Chain Compromise Impacting npm Ecosystem », 23 septembre 2025 :
  <https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem>

**Réglementation**
- NIS2, directive (UE) 2022/2555 : <https://eur-lex.europa.eu/eli/dir/2022/2555/oj> ; article 21 :
  <https://www.nis-2-directive.com/NIS_2_Directive_Article_21.html>
- DORA, règlement (UE) 2022/2554 : <https://eur-lex.europa.eu/eli/reg/2022/2554/oj>
- Cyber Resilience Act, règlement (UE) 2024/2847 : <https://eur-lex.europa.eu/eli/reg/2024/2847/oj> ;
  calendrier de la Commission : <https://digital-strategy.ec.europa.eu/en/policies/cyber-resilience-act>
- NIS2 en France, report du projet de loi (Leto, 6 octobre 2026) :
  <https://www.leto.legal/news/assemblee-nationale-report-projet-loi-resilience-nis2-octobre-2026>
- Saisine de la Cour de justice, 8 juillet 2026 (Digital Watch) : <https://dig.watch/?p=262266>
- CRA et SaaS (DLA Piper, février 2026) :
  <https://www.dlapiper.com/en/insights/publications/2026/02/cyber-resilience-act-the-fine-line-between-saas-and-digital-products>

**Dans le dépôt :** `mesure/resultats.md`, `demo/script.md`, `demo/reseau.md`,
`infra/aws/verifier_h3.sh`, `verifier_m1.sh`, `verifier_compromission.sh`, `docs/points/`.

## 10. Reproduire

- **Tests :** `python -m pytest -q` à la racine du dépôt (551 verts au 2026-10-11).
- **Mesure :** `python3 -I mesure/mesurer.py` donne la ligne 1 (statique, les échantillons sont lus,
  jamais exécutés). Les trois lignes : `mesurer.py --echantillons <Datadog> --cache <rapports> --llm`,
  avec les rapports de sandbox de `mesure/rapports_sandbox/` et Ollama ; la commande exacte est dans
  `docs/points/2026-10-11-B-mesure-finale.md`. `mesure/llm_paquet.py` : le vrai LLM sur une version
  de PyPI.
- **Démo complète :** `demo/script.md`, section H16, sur l'infra AWS (`infra/README.md`).
- **Cloisonnement :** `infra/aws/verifier_h3.sh`, `verifier_m1.sh`, `verifier_compromission.sh`.
