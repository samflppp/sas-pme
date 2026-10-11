# Dossier business : marché, concurrence, valeur, client, pitch

Pour préparer le pitch et le deck, et pour répondre au jury sur l'originalité, l'impact et la
viabilité. Chaque chiffre a sa source (§ 12) ; une **hypothèse** est marquée comme telle. Recherche
faite le 2026-10-11.

## 1. La synthèse, honnêtement

- **Le problème est réel, grandit vite et coûte cher.** 454 600 paquets malveillants nouveaux en
  2025 (+75 % en un an, Sonatype). Un tiers est impliqué dans 30 % des violations de données, deux
  fois plus qu'un an plus tôt (Verizon). Une compromission par la chaîne d'approvisionnement coûte en
  moyenne 4,91 M$ et met 267 jours à être détectée et contenue (IBM).
- **Le marché est validé, et encombré.** Socket et Aikido valent chacun 1 Md$ (2026), Chainguard
  3,5 Md$ (2025). Les investisseurs y croient ; les grands acteurs existent.
- **Notre idée phare, le délai, n'est plus nouvelle.** Depuis 2025-2026, npm, pnpm, uv et Dependabot
  savent attendre avant d'installer une nouvelle version ; Dependabot attend **3 jours par défaut**
  depuis juillet 2026. Aikido Safe Chain, gratuit, bloque les paquets de moins de 48 h. **Ne pas
  pitcher « on a inventé le délai ».** Pitcher plutôt : « tout le monde reconnaît maintenant que le
  délai marche ; nous sommes les seuls à l'imposer au niveau du réseau et à utiliser ces jours pour
  analyser. »
- **Ce qui est vraiment différent chez nous** (§ 4) :
  1. le délai et le contrôle sont **imposés par le réseau**, pas par un réglage que chaque projet,
     chaque développeur ou chaque **agent IA** peut oublier ou contourner ;
  2. les 3 jours **servent** : analyse statique, sandbox avec leurres, IA locale, signature ;
  3. **tout est sur place** : ni le code, ni la liste des dépendances ne partent chez un éditeur
     SaaS américain ;
  4. **après coup**, on révoque, et l'inventaire dit quels serveurs ont la version.
- **Notre vraie fenêtre :** les PME tech européennes qui vendent à des clients régulés, veulent une
  solution souveraine et n'ont ni le budget ni l'équipe pour Sonatype ou JFrog.
- **Notre vrai risque :** qu'un acteur bien financé (Aikido, européen, déjà orienté PME) ajoute un
  mode « appliance sur site ». Notre réponse : l'architecture cloisonnée et le tout-local, difficiles
  à greffer sur un SaaS.

## 2. Le problème, en chiffres

| Chiffre | Ce qu'il dit | Source |
|---|---|---|
| **454 600** paquets malveillants nouveaux en 2025, **+75 %** sur un an ; **1,233 million** connus au total (npm, PyPI, Maven, NuGet, Hugging Face) | le volume dépasse toute relecture humaine | Sonatype, rapport 2026 |
| **9 800 milliards** de téléchargements open source par an | la surface d'attaque | Sonatype |
| Dans **30 %** des violations, un tiers est impliqué (15 % un an plus tôt) | la chaîne d'approvisionnement est devenue une porte d'entrée majeure | Verizon DBIR 2025 (12 195 violations analysées) |
| **4,91 M$** de coût moyen d'une compromission par un fournisseur ou la chaîne d'approvisionnement (moyenne toutes causes : 4,44 M$) ; **267 jours** pour la détecter et la contenir, le plus long de tous les vecteurs | cher, et très lent à voir | IBM Cost of a Data Breach 2025 (résumés) |
| **8 attaques sur 10** étudiées ont été exploitables **moins d'une semaine** ; 7 sur 10 moins de 24 h | un délai de quelques jours en arrête la plupart | W. Woodruff, « We should all be using dependency cooldowns », 2025 |
| **19,7 %** des paquets recommandés par les IA de code **n'existent pas** (5,2 % pour les modèles commerciaux, 21,7 % pour les modèles ouverts) | un attaquant enregistre ces noms : c'est le « slopsquatting » | Spracklen et al., USENIX Security 2025 |
| **59 %** des petites entreprises déclarent une cyberattaque dans l'année (7 pays, ~6 000 entreprises) | les PME sont visées | Hiscox Cyber Readiness Report 2025 |

**Quatre cas réels, à raconter :**
- **ultralytics (PyPI, décembre 2024)** : la 8.3.41 installe un mineur de cryptomonnaie ; la 8.3.42,
  publiée **pour corriger**, contient le même code ; la 8.3.45 et la 8.3.46 suivent avec un jeton
  volé. Fenêtres : 12 h puis 1 h (Woodruff). Le paquet compte environ 60 millions de téléchargements
  (ReversingLabs).
- **Shai-Hulud (npm, septembre 2025)** : un ver, plus de 500 paquets, vol des jetons GitHub et des
  clés AWS, GCP et Azure. La CISA demande de revenir aux versions d'avant le 16 septembre 2025.
- **Shai-Hulud 2.0 (novembre 2025)** : environ 750 à 800 paquets, plus de 25 000 dépôts GitHub
  servant à exfiltrer, des centaines de milliers de secrets exposés (Wiz, GitGuardian, Check Point ;
  les chiffres varient selon les méthodes).
- **Mini Shai-Hulud (mai 2026)** : TanStack, Mistral AI, UiPath et plus de 160 paquets npm et PyPI.
  Les versions piégées sortent du **vrai pipeline de publication**, avec des **attestations de
  provenance valides** (SLSA niveau 3). 84 archives TanStack publiées en 6 minutes le 11 mai,
  attaque révélée le 12. **Leçon : une signature d'origine ne prouve plus qu'une version est
  saine.**

## 3. Ce qui existe déjà

| Famille | Acteurs | Ce qu'ils font | Prix publics | Limite pour notre client |
|---|---|---|---|---|
| **Délai natif, gratuit** | pnpm `minimumReleaseAge` (10.16, 2025), npm `min-release-age` (11.10, février 2026), uv `exclude-newer` relatif (0.9.17), pip `--uploaded-prior-to` (26.0), Dependabot `cooldown` (3 jours par défaut depuis juillet 2026), Renovate `minimumReleaseAge` | ne prennent pas une version trop récente | gratuit | un réglage **par projet et par outil**, que chacun peut oublier ou retirer ; le délai attend, il **n'analyse rien** ; rien n'empêche un serveur d'aller sur PyPI |
| **Pare-feu de paquets sur le poste** | Aikido Safe Chain (npm, pip, uv, poetry), Socket Firewall | bloquent les paquets connus comme malveillants, et ceux de moins de 48 h (Safe Chain) | gratuit | sur le poste et en CI, à installer partout ; s'appuient sur la base de l'éditeur, dans son cloud |
| **Plateformes SaaS orientées développeurs** | Socket, Aikido, Snyk, Endor Labs | analyse des dépendances, détection de malwares, tableaux de bord, SBOM | Socket : 25 $/dév/mois (min. 5), 50 $ en Business ; Aikido : forfaits d'environ 300 à 1 050 $/mois pour 10 utilisateurs (agrégateurs, à confirmer) | **SaaS** : la liste des dépendances part chez l'éditeur ; pas de cloisonnement réseau ; pas de serveur coupé d'Internet |
| **Dépôts d'entreprise avec quarantaine** | Sonatype Nexus + Repository Firewall, JFrog Artifactory + Curation / Xray | un dépôt interne qui fait proxy, met en quarantaine ce qui viole une politique, relâche ce qui est confirmé sain | pas de prix public ; Curation réservé aux offres hautes | conçus pour les grandes équipes : coût, intégration et administration hors de portée d'une PME de 20 à 80 personnes |
| **Paquets reconstruits depuis les sources** | Chainguard Libraries (Python depuis 2025, aussi Java et JavaScript) | un index qui reconstruit chaque paquet dans une infrastructure durcie ; inclut un délai réglable | pas de prix public | catalogue limité ; service cloud ; on change de source sans contrôler ce qui sort ni où c'est installé |
| **Cadres et pratiques des grands groupes** | Microsoft S2C2F (repris par l'OpenSSF) : ingérer via un dépôt interne, inventorier, imposer, auditer, analyser, reconstruire | la méthode que suivent les grands groupes : rien n'entre sans passer par un dépôt interne contrôlé | gratuit (méthode) | une méthode, pas un produit : il faut une équipe pour l'appliquer |

**Les signaux du marché** : Socket, 60 M$ en mai 2026 pour 1 Md$ de valorisation ; Aikido (Belgique),
60 M$ en janvier 2026 pour 1 Md$ ; Chainguard, 356 M$ en avril 2025 pour 3,5 Md$ ; Endor Labs, 93 M$
en avril 2025. Les estimations de taille de marché vont de **2,2 à 7,2 Md$ en 2025**, avec 11 à 29 %
de croissance par an selon la définition (cabinets d'études payants, méthodes peu publiées : à citer
comme une fourchette, jamais comme un chiffre exact).

## 4. Sommes-nous novateurs ? Ce qui est neuf, ce qui ne l'est pas

**Pas neuf, et il faut le dire avant le jury :**
- le délai (tous les gestionnaires de paquets l'ont maintenant) ;
- l'analyse statique de paquets, la détection de typosquat (Socket, Aikido, Sonatype) ;
- le dépôt interne avec quarantaine (Sonatype, JFrog ; c'est la pratique S2C2F des grands groupes) ;
- la sandbox d'analyse de paquets (plusieurs éditeurs en ont une, dans leur cloud).

**Neuf, ou rare, dans notre combinaison :**
1. **Le délai imposé par le réseau.** Ailleurs, le délai est une option que chaque projet active.
   Chez nous, les serveurs n'ont **pas de route vers Internet** : ils ne peuvent prendre que ce que
   la passerelle a reçu, vérifié et signé. Rien à configurer sur les postes, rien à oublier.
2. **Les jours d'attente servent à vérifier.** Le délai natif attend ; nous analysons pendant ce
   temps : code, comportement en sandbox avec de faux secrets, explication de l'IA locale.
3. **Tout local, IA comprise.** Socket, Aikido, Snyk et Endor sont des SaaS : la liste exacte de vos
   dépendances, donc vos faiblesses, part chez eux. Chez nous, ne sortent que des noms de paquets et
   des numéros de version publics.
4. **La signature comme preuve d'entrée, et la révocation comme suite.** Une version n'entre que
   signée par la plateforme ; un avis tombé après coup la retire partout, et l'inventaire dit quels
   serveurs l'ont téléchargée.
5. **Une barrière pour les agents IA.** Les agents de code installent eux-mêmes des paquets, et
   20 % des noms qu'une IA propose n'existent pas. Un délai réglé par projet ne protège pas un agent
   qui lance `pip install` sur un serveur ; un serveur sans route vers Internet, si.
6. **Le verdict expliqué en français à un CTO**, avec ses preuves, et l'IA qui ne décide jamais.

**Verdict honnête :** aucune brique n'est une invention ; **l'assemblage, la cible et le
positionnement le sont**. Nous apportons la discipline des grands groupes (S2C2F, dépôt interne,
quarantaine) à une PME qui n'a pas l'équipe pour l'appliquer, sous forme d'une boîte, sans cloud.

## 5. Notre plus-value face à chacun

| Face à… | Ce qu'ils font mieux | Ce que nous faisons mieux |
|---|---|---|
| un délai natif (Dependabot, pnpm, uv) | gratuit, déjà là | imposé à toute la machine et à tout l'outil, pas par projet ; analyse pendant l'attente ; preuve et journal |
| Aikido Safe Chain / Socket Firewall | gratuits, base de menaces mondiale, mis à jour en continu | rien à installer sur chaque poste ; le serveur ne peut pas les contourner ; pas de dépendance à un cloud |
| Socket, Aikido, Snyk (SaaS) | couverture large (plusieurs langages, SAST, secrets, conteneurs), interface mûre, équipes de recherche | souveraineté (rien ne part) ; cloisonnement réseau démontrable ; révocation et inventaire sur site |
| Sonatype, JFrog | robustes, éprouvés, tous écosystèmes, intégrés partout | prix, simplicité et installation à la taille d'une PME ; IA locale qui explique ; journal signé |
| Chainguard Libraries | paquets reconstruits depuis les sources, très sûrs | on garde l'écosystème entier, pas un catalogue ; contrôle sur site de ce qui entre et où c'est installé |

**À ne jamais dire :** « on détecte mieux que Socket » (non mesuré), « personne ne fait ça » (faux),
« conforme NIS2 » (aucun outil ne rend conforme seul).

## 6. Ce que le logiciel apporte qu'un humain n'apporte pas

| Un humain… | Le logiciel… | Le chiffre qui le montre |
|---|---|---|
| relit quelques paquets par jour, au mieux | analyse chaque version de chaque dépendance, transitive comprise | 454 600 paquets malveillants nouveaux en 2025 |
| réagit en heures ou en jours, et dort la nuit | applique le délai à chaque version, sans exception ni oubli, 24 h sur 24 | 7 attaques sur 10 exploitables moins de 24 h |
| lit le code, mais ne le voit pas s'exécuter | regarde le paquet agir en sandbox : fichiers lus, DNS, connexions, avec de faux secrets uniques | la 1.2 de la démo : faux `~/.aws/credentials` lu, DNS de l'attaquant vu |
| se fatigue, juge différemment d'un jour à l'autre | applique la même politique, écrite, à chaque version | 0 fausse alerte sur 98 paquets sains en statique (notre mesure) |
| oublie ce qu'il a décidé et pourquoi | garde chaque décision dans un journal signé, vérifiable par un auditeur | « Vérifier la chaîne » |
| ne sait pas, après un avis, quels serveurs ont la version | révoque partout et dit où la version est installée | page « Inventaire » |
| tombe dans le piège de l'urgence | n'accepte aucune version, même « correctif urgent », sans le délai et l'analyse | ultralytics 8.3.42 |
| ne peut pas surveiller ce que ses agents IA installent | impose la même barrière à un agent qu'à un humain | 19,7 % de paquets inventés par les IA de code |

**Ce que l'humain garde, et c'est voulu :** la décision dans le doute (« à revoir »), et la levée
d'une alerte. Le logiciel fait le travail répétitif et rend la décision humaine rare, rapide et
motivée.

**Ce que notre mesure montre (2026-10-10)** : l'analyse statique seule arrête **93 paquets
malveillants sur 128 (73 %)** sans aucune fausse alerte sur **98 paquets sains** ; le nom seul n'en
arrête que **3 %**. La mesure finale à trois colonnes (+ sandbox, + IA) est à venir (B).

## 7. Le client type

**L'entreprise**
- startup ou PME tech de **20 à 80 personnes**, dont **5 à 25 développeurs** Python ou JavaScript ;
- elle vend à des clients **régulés** (finance, assurance, santé, secteur public) qui lui envoient
  des questionnaires de sécurité, ou à des clients qui exigent l'hébergement en Europe ;
- pas de RSSI : le **CTO** porte la sécurité, souvent avec un infogérant ;
- elle a des serveurs qu'elle peut cloisonner (sur site, cloud privé, ou un VPC).

**Les personnes**

| Rôle | Qui | Ce qu'il veut entendre |
|---|---|---|
| décideur | CTO, parfois le CEO | « vous répondez au questionnaire du grand compte avec une preuve, pas une promesse » |
| utilisateur | lead dev, DevOps | « rien ne change pour vous : `pip install` marche, juste avec 3 jours de recul » |
| prescripteur | infogérant, auditeur ISO 27001, courtier ou assureur cyber | « une mesure concrète sur la chaîne d'approvisionnement, et un journal à montrer » |
| bloqueur possible | développeur pressé | « une vraie urgence se lève en un geste tracé, sans sauter l'analyse » |

**Les déclencheurs d'achat** : un questionnaire de sécurité d'un grand compte ; un audit ISO 27001 ou
SOC 2 ; une exigence de souveraineté d'un client public ; un incident dans l'actualité (Shai-Hulud,
TanStack) ; une due diligence de levée de fonds.

**Le cadre réglementaire** (vérifié, `defense.md` § 8) :
- NIS2 demande aux entités assujetties de sécuriser leur chaîne d'approvisionnement (art. 21) ; nos
  clients sont touchés **par ricochet**. Elle n'est pas encore transposée en France au
  6 octobre 2026 ;
- DORA s'applique depuis janvier 2025 aux entités financières et à leurs prestataires TIC ;
- le CRA impose depuis septembre 2026 le signalement des vulnérabilités exploitées, et en
  décembre 2027 la documentation des composants.

**Qui n'est pas client** : les entreprises qui ne développent pas ; les grandes entreprises déjà
équipées (Sonatype, JFrog) ; les équipes de moins de 5 développeurs (un délai natif gratuit leur
suffit).

## 8. La taille du marché

**Vue de haut** : 2,2 à 7,2 Md$ dans le monde en 2025 selon les cabinets (§ 3). Fourchette large,
méthodes opaques : utile pour dire « marché de plusieurs milliards, en croissance à deux chiffres »,
pas plus.

**Vue du bas, la France d'abord** (hypothèses à affiner, données de 2017 pour l'INSEE) :

| Étape | Chiffre | Source ou hypothèse |
|---|---|---|
| Entreprises « information et communication » de 10 à 249 salariés | ≈ 7 800 (6 400 de 10 à 49, 900 de 50 à 99, 500 de 100 à 249) | INSEE, *Les entreprises en France*, édition 2017 |
| Start-up actives de la French Tech | 18 000, 450 000 emplois | Mission French Tech, panorama 2025 |
| Part qui développe, a 5 à 25 développeurs et vend à des clients exigeants | **hypothèse : 30 à 50 %** des entreprises de la première ligne | à valider par des entretiens |
| **Cible française** | **≈ 2 500 à 4 000 entreprises** | hypothèse |
| Prix moyen | 500 €/mois, soit **6 000 €/an** | hypothèse (§ 9) |
| **Marché adressable en France** | **≈ 15 à 24 M€ par an** | calcul |
| Europe (Allemagne, Benelux, Espagne, Italie) | ordre de grandeur : 4 à 6 fois la France | **hypothèse**, à vérifier |

**Objectif réaliste, et à dire comme tel** : 10 à 30 clients la première année, soit **60 000 à
180 000 € de revenu récurrent annuel**. Ce n'est pas une projection financière, c'est l'ordre de
grandeur d'un premier pilote commercial.

## 9. Le modèle économique

- **Abonnement mensuel, forfaitaire par entreprise**, pas par développeur : **300 à 800 €/mois**
  selon le nombre de serveurs et d'écosystèmes. **Hypothèse à tester.**
- **Repère de prix** : Socket coûte 25 $ par développeur et par mois (375 $ pour 15 développeurs) ;
  Aikido, de l'ordre de 300 à 1 050 $ par mois pour 10 utilisateurs. Notre prix est **dans la même
  zone** ; nous ne sommes pas moins chers, nous vendons autre chose (souveraineté, cloisonnement).
- **Installation** : une appliance (ou une image de machine virtuelle) livrée chez le client, ou
  hébergée chez un infogérant européen. Frais de mise en service possibles.
- **Coût de revient** : un serveur CPU, sans GPU (le LLM 7B tourne sur CPU, 50 à 60 s par version) ;
  la mise à jour de la base de menaces et du RAG. **À chiffrer.**
- **Canaux** : les **infogérants** (un contrat, plusieurs clients ; la console multi-clients est sur
  la feuille de route), les **assureurs cyber** et les **auditeurs ISO** comme prescripteurs, les
  réseaux French Tech et les incubateurs.

## 10. Les risques business, sans fard

| Risque | Probabilité | Ce qu'on fait |
|---|---|---|
| Le délai devient gratuit partout (c'est déjà le cas) et le client trouve que « ça suffit » | forte | vendre le cloisonnement, l'analyse et la preuve, pas le délai |
| Un acteur financé (Aikido, Socket) lance une version sur site | moyenne | aller vite sur la niche souveraine et les infogérants ; l'architecture cloisonnée est notre cœur, pas une option |
| Une PME n'a pas de serveurs à cloisonner (tout en SaaS, tout en serverless) | forte pour une partie de la cible | cibler celles qui ont des serveurs ou un VPC ; étendre aux exécuteurs de CI et aux images |
| Les développeurs contournent (poste personnel, `pip install` depuis un portable) | moyenne | le cloisonnement protège les serveurs, pas les postes ; un mode « poste » viendra après |
| Le coût d'installation et de support dépasse le prix | moyenne | appliance standard, installation en une commande (priorité n° 1 après le hackathon) |
| La mesure ne montre pas d'apport de l'IA par rapport aux règles | à mesurer | la mesure finale (B) tranche ; si l'IA n'ajoute rien en détection, elle reste pour l'explication, et on le dit |

## 11. Pistes, ouvertes

1. **La barrière des agents IA.** Vendre la plateforme comme « le seul endroit où vos agents de code
   peuvent installer un paquet ». Les agents lancent `pip install` seuls ; 20 % des noms qu'une IA
   propose n'existent pas. Angle très actuel, peu occupé.
2. **Le dossier de preuve pour les questionnaires.** Exporter, en un clic, la réponse à « comment
   contrôlez-vous vos dépendances ? » : politique, délai, chiffres du journal, dernières décisions.
   Ce que le CTO achète vraiment, c'est ce document.
3. **Les infogérants.** Une plateforme pour vingt clients ; prix par client ; la console
   multi-clients. Le canal le plus court vers les PME.
4. **Les assureurs cyber.** Une baisse de prime contre l'installation, comme pour une alarme. Les
   PME françaises couvertes reculent (à vérifier sur le rapport Hiscox 2026) : un argument pour
   l'assureur comme pour le client.
5. **Le secteur public et la santé.** Exigences de souveraineté : le tout-local est un critère
   d'achat, pas un détail.
6. **Les modèles d'IA.** Sonatype compte déjà Hugging Face parmi les dépôts de malwares : le même
   sas pour les modèles téléchargés.
7. **Les images Docker et les exécuteurs de CI** : la même barrière là où les attaques de 2025-2026
   ont frappé (pipelines GitHub Actions).
8. **La télémétrie entre clients** : une version vue saine chez dix clients peut sortir plus vite
   chez le onzième ; une version bloquée chez l'un l'est chez tous.
9. **L'export SBOM** de l'inventaire, pour les clients soumis au CRA.

## 12. Le pitch (3 minutes)

**L'idée à faire retenir en une phrase :** « Vos serveurs n'installent que ce qu'on a vérifié, et
même vos agents IA ne peuvent pas passer à côté. »

**Accroche, à choisir (15 s) :**
- **A, la signature trompée :** « Le 11 mai 2026, TanStack, une bibliothèque JavaScript très utilisée,
  publie 84 versions piégées en 6 minutes. Par son propre pipeline, avec des
  signatures de provenance valides. Les signatures ne suffisent plus. »
- **B, le correctif piégé :** « En décembre 2024, ultralytics publie un correctif d'urgence pour une
  version piégée. Le correctif était piégé aussi. Ceux qui ont mis à jour vite ont réinstallé le
  malware. »
- **C, les agents :** « Demain matin, votre agent IA va installer des paquets sur vos serveurs. Une
  fois sur cinq, l'IA propose un paquet qui n'existe pas, et quelqu'un l'a peut-être déjà
  enregistré. »

Conseil : **A ou B** pour le jury cybersécurité (fait vérifiable, frappant) ; **C** en ouverture de
la partie « ce qui vient ».

**Déroulé :**

| Temps | Ce qu'on dit | Ce qu'on montre |
|---|---|---|
| 0:00–0:15 | accroche | une date, un chiffre |
| 0:15–0:40 | le problème : 454 600 paquets malveillants en 2025 ; 30 % des violations passent par un tiers ; les PME n'ont pas d'équipe | trois chiffres, pas plus |
| 0:40–1:05 | l'idée : le délai marche (8 attaques sur 10 durent moins d'une semaine), mais il faut l'imposer et l'utiliser. Une plateforme vérifie ; une passerelle sans Internet ; des serveurs qui ne prennent que ce qui est signé | le schéma réseau |
| 1:05–2:05 | la démo (vidéo) : `curl pypi.org` échoue sur le serveur ; la 1.2 bloquée avec ses preuves, l'IA explique et cite ; une publication forgée refusée ; la révocation et l'inventaire | la vidéo de C |
| 2:05–2:25 | les chiffres : 73 % arrêtés en statique, 0 fausse alerte ; la mesure à trois colonnes | la diapositive de B |
| 2:25–2:45 | pourquoi nous : tout local, cloisonnement prouvé, IA qui ne décide jamais ; pour les PME que Sonatype et JFrog ne servent pas | une ligne par point |
| 2:45–3:00 | la suite : appliance, infogérants, agents IA ; la phrase de fin | « Vos serveurs n'installent que ce qu'on a vérifié. » |

**Les chiffres à dire, et pas plus** : 454 600 paquets malveillants en 2025 ; 30 % des violations
via un tiers ; 8 attaques sur 10 durent moins d'une semaine ; 73 % arrêtés sans fausse alerte. Trop
de chiffres en 3 minutes, et le jury n'en retient aucun.

**À éviter dans le pitch** : « on a inventé le délai » ; « conforme NIS2 » ; « on détecte mieux que
X » ; un chiffre de marché présenté comme exact.

## 13. Sources

Consultées le 2026-10-11. Les rapports payants sont cités d'après leurs communiqués ou des résumés :
vérifier le rapport original avant de citer un chiffre devant le jury.

**Menace**
- Sonatype, State of the Software Supply Chain 2026 :
  <https://www.sonatype.com/state-of-the-software-supply-chain/2026/open-source-malware> ;
  communiqué (75 %, 9 800 milliards) :
  <https://finance.yahoo.com/news/sonatype-research-reveals-oss-malware-110000602.html>
- Verizon, 2025 Data Breach Investigations Report :
  <https://verizon.com/about/news/2025-data-breach-investigations-report>
- IBM, Cost of a Data Breach 2025 (résumé) :
  <https://www.bakerdonelson.com/ten-key-insights-from-ibms-cost-of-a-data-breach-report-2025>
- W. Woodruff, We should all be using dependency cooldowns :
  <https://blog.yossarian.net/2025/11/21/We-should-all-be-using-dependency-cooldowns>
- Spracklen et al., We Have a Package for You! (USENIX Security 2025) :
  <https://arxiv.org/abs/2406.10279v3>
- Hiscox Cyber Readiness Report 2025 : <https://www.hiscoxgroup.com/node/53166>
- ultralytics : <https://www.reversinglabs.com/blog/compromised-ultralytics-pypi-package-delivers-crypto-coinminer>
- Shai-Hulud, CISA :
  <https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem>
- Shai-Hulud 2.0 : <https://blog.checkpoint.com/research/shai-hulud-2-0-inside-the-second-coming-the-most-aggressive-npm-supply-chain-attack-of-2025/> ;
  <https://www.bleepingcomputer.com/news/security/shai-hulud-20-npm-malware-attack-exposed-up-to-400-000-dev-secrets/>
- Mini Shai-Hulud (TanStack, Mistral) : <https://tanstack.com/blog/npm-supply-chain-compromise-postmortem> ;
  <https://docs.mistral.ai/resources/security-advisories/MAI-2026-002> ;
  <https://orca.security/resources/blog/tanstack-npm-supply-chain-worm/>

**Concurrence et outils**
- pnpm `minimumReleaseAge` : <https://socket.dev/blog/pnpm-10-16-adds-new-setting-for-delayed-dependency-updates>
- Dependabot, 3 jours par défaut : <https://thehackernews.com/2026/07/github-adds-3-day-dependabot-cooldown.html>
- uv `exclude-newer` : <https://pydevtools.com/handbook/how-to/how-to-use-exclude-newer-for-reproducible-python-environments/>
- Aikido Safe Chain : <https://github.com/AikidoSec/safe-chain>
- Socket, prix : <https://socket.dev/pricing>
- Aikido, prix (agrégateur) : <https://codeant.ai/blogs/aikido-security-pricing>
- Sonatype Repository Firewall : <https://www.sonatype.com/products/sonatype-repository-firewall>
- Chainguard Libraries for Python :
  <https://www.chainguard.dev/unchained/announcing-chainguard-libraries-for-python-malware-resistant-dependencies-built-securely-from-source>
- Microsoft S2C2F : <https://github.com/ossf/s2c2f/blob/main/specification/framework.md>

**Marché et financements**
- Mordor Intelligence : <https://www.mordorintelligence.com/industry-reports/software-supply-chain-security-platforms-market>
- Custom Market Insights : <https://www.globenewswire.com/news-release/2025/03/19/3045152/0/en/Latest-Global-Software-Supply-Chain-Security-Market-Size-Share-Worth-USD-3-27-Billion-by-2034-at-a-10-9-CAGR-Custom-Market-Insights-Analysis-Outlook-Leaders-Report-Trends-Forecast-.html>
- Socket, série C : <https://radar.offseq.com/threat/socket-raises-60-million-at-1-billion-valuation-b351b16d>
- Aikido, série B : <https://siliconangle.com/2026/01/14/aikido-security-raises-60m-series-b-1b-valuation-unify-application-security/>
- Chainguard, série D : <https://fortune.com/2025/04/23/exclusive-chainguard-secures-356-million-series-d-as-valuation-soars-to-3-5-billion>
- Endor Labs, série B : <https://www.lw.com/en/news/2025/04/latham-watkins-advises-on-endor-labs-us93-million-series-b-financing-round>
- French Tech, panorama 2025 : <https://lafrenchtech.gouv.fr/fr/panoramafrenchtech2025/>
- INSEE, Les entreprises en France 2017 : <https://www.insee.fr/fr/statistiques/fichier/3152833/ENTFRA17.pdf>
