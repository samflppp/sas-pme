# Contexte du projet

À lire en premier, par une personne comme par un agent (Claude Code, Kiro). Les autres documents
détaillent : `architecture.md`, `contrats.md`, `roadmap.md`, `organisation.md`, `sauvegardes.md`.

## 1. En une phrase

Une **plateforme agréée**, seule machine de la PME reliée à Internet, qui attend 3 jours chaque nouvelle
version de paquet pip ou npm, l'analyse localement (code, sandbox, IA), puis la publie, signée, dans
une **passerelle sans Internet** où les serveurs sensibles s'approvisionnent. Les serveurs ne voient
jamais la dernière version publiée sur Internet, seulement la dernière version **vérifiée**.

**Accroche.** « Vos serveurs n'installent que ce qu'on a vérifié. »

**Sens du mot « sas ».** C'est un sas de sécurité, pas un SaaS : tout tourne chez le client. Le nom du
produit reste à choisir.

## 2. Le hackathon

- **Track 3 « Open Track »** : IA × cybersécurité, côté défense. Nos axes du sujet : la chaîne
  d'approvisionnement logicielle (n° 2) et les PME sans équipe cyber (n° 4).
- **Grille du jury :**

  | Critère | Poids |
  |---|---|
  | Importance et originalité du problème | 25 % |
  | Efficacité défensive **démontrée**, chiffres à l'appui | 25 % |
  | Impact | 20 % |
  | Viabilité économique | 20 % |
  | Pitch et démo | 10 % |

- **Livrables :**
  - un dépôt de code ;
  - une vidéo de démo ;
  - un deck, avec une diapositive « why this problem » et une diapositive « what's next » (premiers
    clients, 6 mois) ;
  - une fiche de défense ;
  - un **PoC qui marche sur un scénario défensif concret**.
- **Objectif de l'équipe : une démo qui est un vrai MVP**, pas un produit complet. On ne va pas
  plus loin que ce qui sert la démo.

## 3. Le problème

Les PME et startups qui développent installent chaque jour des paquets pip et npm que personne ne
relit, directement depuis Internet, sur des serveurs qui portent leurs données sensibles. Une version
piégée suffit : typosquat, mainteneur compromis, ou ultralytics (décembre 2024), ver Shai-Hulud sur npm
(septembre 2025). La plupart de ces versions sont repérées et retirées en quelques heures ou quelques
jours. Ces entreprises n'ont ni RSSI ni SOC.

## 4. Le client idéal

- **Profil :** startup ou PME tech de **20 à 80 personnes**, dont 5 à 25 développeurs Python ou
  JavaScript. Elle vend à des clients régulés (santé, finance, assurance, secteur public) qui lui
  envoient des questionnaires de sécurité. Elle n'a pas de RSSI : c'est le CTO qui porte la sécurité.
- **Pressions :**
  - DORA par ricochet ;
  - NIS2 comme fournisseur ;
  - le CRA si elle vend un logiciel ;
  - ISO 27001, SOC 2 ou HDS en cours.
- **Déclencheurs d'achat :** un questionnaire d'un grand compte, un audit, un incident dans l'actualité,
  une due diligence de levée de fonds.
- **Qui achète, qui utilise, qui prescrit :**
  - le décideur est le CTO ;
  - l'utilisateur est le lead dev ou le DevOps ;
  - les prescripteurs sont l'infogérant, l'auditeur ISO et l'assureur cyber.
- **Prix (hypothèse à tester) :** 300 à 800 € par mois.
- **Ne sont pas clients :**
  - les PME qui ne développent pas ;
  - les grandes entreprises, qui ont déjà Artifactory ou Sonatype et un SOC ;
  - les équipes de moins de 5 développeurs.

Les textes réglementaires (NIS2, DORA, CRA), leurs dates et l'état de NIS2 en France sont vérifiés et sourcés
dans `defense.md` § 8 (2026-10-11) : citer ceux-là, pas ceux de mémoire.

## 5. Le produit

**Trois zones, un seul passage vers Internet** (détail dans `architecture.md`) :

1. **La plateforme agréée.** Elle est reliée à Internet, sur site ou hors site.
   - Elle offre une interface web, une sorte de « GitHub local » des versions approuvées.
   - Elle porte le pipeline d'analyse : veille, délai de 3 jours, analyse statique, sandbox, LLM local
     avec un RAG sur les failles connues.
   - Elle signe les versions approuvées.
   - Elle relaie les appels d'API autorisés.
2. **La passerelle, la « boîte noire ».** Elle est sur site et **n'a aucun accès à Internet**.
   - Elle tient un dépôt pip et npm des seules versions approuvées et signées.
   - Elle vérifie chaque signature avant de publier une version.
   - Elle remonte l'inventaire de ce que les serveurs utilisent.
3. **Les serveurs sensibles.** Ils n'ont aucun accès à Internet. `pip` et `npm` pointent sur la
   passerelle.

**Le lien plateforme ↔ passerelle :**
- sur le réseau local si les deux sont sur site ;
- par un VPN WireGuard si la plateforme est hors site ;
- dans les deux cas avec une authentification mutuelle (TLS mutuel) et des publications signées.

**Le parcours d'une mise à jour :**
1. inventaire ;
2. nouvelle version détectée ;
3. **3 jours d'attente**, pendant lesquels la veille lit OSV, PyPI, npm et les blogs de chercheurs ;
4. téléchargement ;
5. analyse statique ;
6. installation en sandbox ;
7. verdict du LLM appuyé sur le RAG ;
8. politique déterministe ;
9. signature et publication dans la passerelle.

Un **nouveau paquet** se demande depuis l'interface web. La plateforme prend la dernière version
publiée depuis plus de 3 jours et lui fait suivre le même parcours.

## 6. Principes non négociables

| Principe | Conséquence |
|---|---|
| **Les serveurs sensibles ne parlent jamais à Internet** | tout passe par la passerelle, qui ne parle qu'à la plateforme |
| **Le code décide, l'IA alerte et explique** | un signal du LLM ou d'un article peut monter un risque, jamais approuver ni abaisser |
| **Un texte lu n'est jamais une instruction** | code de paquet, changelog, article, document du RAG : encadrés comme données ; sortie du LLM validée par schéma |
| **Rien n'est publié sans signature** | la passerelle refuse tout manifeste mal signé ou dont un hash diffère |
| **Tout local** | LLM, RAG et sandbox sur la plateforme ; aucun service d'IA dans le cloud |
| **On lit Internet, on ne lui parle pas de vous** | ne sortent vers Internet que des noms de paquets avec leurs versions, et des téléchargements publics |
| **Le journal ne s'efface pas** | journal append-only chaîné par hash |

## 7. Décisions prises, et pourquoi

| Décision | Écarté | Pourquoi |
|---|---|---|
| Cible : PME et startups **qui développent** | PME qui ne développent pas | corpus d'attaques publics, démo nette |
| **pip + npm** dans le produit ; **pip seul dans le MVP**, npm en extension | pip seul | les deux écosystèmes sont attaqués ; npm d'abord coupé si le temps manque |
| **Délai de 3 jours** | 48 h | la plupart des versions piégées sont retirées en quelques jours |
| **Plateforme connectée / passerelle déconnectée** | un proxy en ligne qui filtre en direct | les données sensibles ne touchent jamais Internet ; le cloisonnement se démontre |
| La **plateforme pousse** ; la passerelle ne joint que la plateforme | la passerelle va chercher elle-même | une passerelle compromise ne peut rien tirer d'Internet |
| **Signature Ed25519** des manifestes | confiance dans le seul lien chiffré | une plateforme usurpée ne peut pas publier |
| **Sandbox Docker sans réseau réel**, faux DNS et faux HTTP qui enregistrent, trace des fichiers lus | pas de sandbox | prouve un vol de jetons ou un appel vers l'attaquant, sans rien laisser sortir |
| **RAG local** sur les failles connues | LLM seul | le LLM cite des cas réels ; tout reste local |
| **pypiserver** (pip) et **Verdaccio sans source amont** (npm) dans la passerelle | écrire un registre | on ne réécrit pas ce qui existe |
| **Démo sur AWS** : la plateforme dans un sous-réseau public (GPU), la passerelle et un serveur dans un sous-réseau **privé sans route vers Internet** | tout sur un PC | le cloisonnement est réel et se montre : `curl pypi.org` échoue sur le serveur, `pip install` marche |
| **Un seul dépôt, des branches courtes par tâche** | trois branches longues | voir `organisation.md` |
| « Images approuvées » = **versions de paquets** | images Docker | images Docker : feuille de route |

## 8. Revue critique du cadrage (à garder en tête)

- **Avocat du diable sur l'idée d'origine (« l'IA approuve, tout le trafic ») : verdict STOP.**
  SolarWinds, 3CX et xz arrivaient signés par leur éditeur, donc une IA qui lit du code ne les voit
  pas. Et un boîtier qui déchiffre tout devient la cible n° 1. Ce qu'on a fait en réponse :
  - l'IA n'approuve jamais ;
  - pas de déchiffrement TLS ;
  - un délai, plus une sandbox qui **observe le comportement** ;
  - le cloisonnement réseau ;
  - une mesure chiffrée.
- **Premortem : la cause n° 1 d'échec serait « une règle simple fait aussi bien que l'IA ».** La mesure
  compare donc les contrôles seuls, puis les contrôles + sandbox, puis le tout + LLM/RAG.
- **Concurrence :**
  - Artifactory/Nexus, Sonatype Firewall et Socket existent, mais sont vendus aux grandes équipes de
    dev ;
  - les SASE ne lisent pas un paquet.

  **Notre créneau :** tout local, cloisonnement démontrable, verdict expliqué en français, pour une
  PME sans équipe sécurité.

## 9. Hors du MVP (diapositive « what's next »)

- **La plateforme d'intégration :** installation en une commande, configuration automatique de
  pip/npm sur les serveurs, image d'appliance. C'est ce qui rend le produit « seamless » chez une PME,
  et c'est la priorité n° 1 après le hackathon.
- npm complet, s'il n'est pas fini ;
- images Docker, Maven, NuGet ;
- haute disponibilité ;
- console multi-clients pour les infogérants ;
- télémétrie partagée entre clients (une version libérée après avoir été vue saine ailleurs) ;
- sauvegarde dans le cloud, chiffrée côté client (voir `sauvegardes.md`).

## 10. L'équipe

| Qui | Rôle |
|---|---|
| **A — Sam** (`samflppp`, porteur) | plateforme web : interface, comptes, catalogue, base de données, publication ; pitch |
| **B — Mouabd19** | pipeline et IA : veille, délai, analyse statique, LLM, RAG, politique, mesure |
| **C — STEUSSO** (réseau) | réseau et passerelle : AWS, cloisonnement, passerelle, lien TLS mutuel / WireGuard, signature, sandbox, relais d'API, sauvegardes |
