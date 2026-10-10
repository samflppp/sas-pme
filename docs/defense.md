# Fiche de défense

Pour le jury, et pour nous trois avant les questions. Chaque affirmation renvoie à sa preuve : une
commande de la démo, un fichier du dépôt ou une mesure. Ce qui n'est pas prouvé est dit comme tel
(§ 6). État au 2026-10-11, fin du M2.

## 1. En une phrase

Une **plateforme agréée**, seule machine de la PME reliée à Internet, attend 3 jours chaque nouvelle
version de paquet, l'analyse sur place (code, sandbox, IA locale), puis la publie, **signée**, dans
une **passerelle sans Internet** où les serveurs sensibles s'approvisionnent.

> « Vos serveurs n'installent que ce qu'on a vérifié. »

## 2. Ce que la démo prouve, et comment

| Affirmation | Preuve | Où |
|---|---|---|
| Le serveur sensible n'a pas Internet | `curl --noproxy '*' https://pypi.org` échoue ; aucune route dans le sous-réseau privé, DNS du VPC coupé | démo, étape 1 ; `infra/aws/verifier_h3.sh` (6 contrôles) |
| Il installe pourtant ses paquets | `pip install requests` marche, depuis la passerelle | démo, étape 1 |
| Il ne reçoit que ce qui a été publié | `pip install flask` : introuvable (pypiserver sans repli vers pypi.org) | `verifier_h3.sh` |
| Une version saine passe, après son délai | 1.1 : en attente, analysée, approuvée, signée, publiée ; `pip install -U` | démo, étape 2 |
| Une version piégée est bloquée, avec ses preuves | 1.2 : statique (`exfiltration`, `__init__.py:23`), sandbox (DNS de l'attaquant, faux `~/.aws/credentials` lu), explication du LLM qui cite CWE-522 et T1552.005 | démo, étape 3 ; répétition AWS de C |
| Le doute va à un humain, pas à la machine | 1.3 : un seul signal FORT (tunnel ngrok jamais appelé) : « à revoir » ; l'admin tranche avec une raison ; une seconde décision simultanée est refusée | démo, étape 7 |
| Une publication forgée est refusée | `demo/forger.sh` : `passerelle 401 : signature invalide` | démo, étape 5 |
| Un avis tombé après coup se traite | révocation depuis la fiche, archives retirées de la passerelle ; `/inventaire` signale « révoquée depuis, et téléchargée N fois » | démo, étape 4 |
| Les API sortantes sont contrôlées | depuis le serveur : `api.github.com` 200, `pypi.org` 403 (relais en liste fermée, sans déchiffrement) | démo, étape 1 |
| Le journal n'est pas réécrit en silence | « Vérifier la chaîne » : intègre ; une entrée modifiée casse la chaîne à son numéro | démo, étape 6 ; `tests/plateforme/test_journal_hmac.py` |

Le code est testé : **518 tests verts** au dernier point de B (2026-10-11). Chaque test neuf a été
vu rouge avant le code, puis le code a été cassé exprès (mutations) pour vérifier qu'un test tombe.

## 3. Les chiffres

**Mesure au 2026-10-10** (`mesure/resultats.md`, `python3 -I mesure/mesurer.py`). Une version est
arrêtée si un contrôle lève un signal FORT ou BLOQUANT.

| Contrôles | Détection (malveillantes arrêtées) | Fausses alertes (saines arrêtées) |
|---|---|---|
| Nom seul (typosquat), corpus OpenSSF | 1 / 30 (3 %) | 0 / 50 (0 %) |
| Contrôles statiques (nom + code), Datadog + sains | 93 / 128 (73 %) | 0 / 98 (0 %) |

**À reprendre de la mesure finale de B (M3)** : les trois colonnes (contrôles seuls ; + sandbox ;
+ LLM/RAG), détection et fausses alertes. Elle répond à la question qui tuerait le projet : « une
règle simple fait-elle aussi bien que l'IA ? » (premortem, `contexte.md` § 8). Ne citer au jury que
les chiffres de ce fichier, avec leur date.

**Ce que disent les chiffres actuels, honnêtement :**
- le nom seul ne suffit pas (3 %) : la plupart des paquets malveillants ne copient pas un nom connu ;
- les contrôles statiques arrêtent 73 % sans fausse alerte ; ils manquent 35 versions, dont
  **ultralytics 8.3.41, 8.3.42 et 8.3.46** : c'est le rôle du délai et de la sandbox ;
- le délai ne se mesure pas sur ce corpus : il dépend de la vitesse de retrait de chaque version.

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
Les versions piégées sont le plus souvent repérées et retirées en quelques heures ou quelques jours
(ultralytics en décembre 2024, le ver Shai-Hulud sur npm en septembre 2025). Pendant le délai, la
veille lit OSV, PyPI et les flux de chercheurs. Le délai est réglable (`SAS_DELAI`).

**« Et un correctif de sécurité urgent ? 3 jours, c'est long. »**
Aujourd'hui, le délai s'applique à toutes les versions : **pas de voie d'urgence dans le MVP** (§ 6).
La réponse prévue : un admin lève le délai d'une version précise, avec une raison. Le reste du
parcours ne change pas (statique, sandbox, LLM, signature), et le geste est inscrit au journal.

### L'efficacité défensive (25 %)

**« Une IA qui lit du code se trompe, ou se fait manipuler. »**
D'où la règle centrale : **le code décide, l'IA alerte et explique.**
- Une politique déterministe décide (`plateforme/pipeline/politique.py`) : un signal BLOQUANT
  bloque, un signal FORT met « à revoir », sinon la version est approuvée.
- Le LLM ne peut lever qu'un signal FORT au plus : jamais approuver, jamais bloquer, jamais abaisser
  un autre signal. Les types le refusent (`commun/modeles.py`).
- Un signal FORT du LLM ne compte que s'il s'appuie sur ce que le paquet a montré (une ligne, un
  domaine, un élément de la sandbox) ; sinon il redescend à MOYEN. Cette règle vient de deux fausses
  alertes vues en répétition, sur certifi et idna (point B H16).
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
alors ce qu'elle peut faire.

**« Et si la plateforme est compromise ? »**
Réponse détaillée de C : `demo/reseau.md` § 3. En résumé :
- une plateforme **usurpée** ne publie rien : il lui faut le certificat du lien **et** la clé de
  signature (étape 5 de la démo) ;
- une plateforme **réellement prise** peut signer une version piégée avec la vraie clé. Elle ne
  donne pas Internet aux serveurs, ne lit pas leurs données, et la passerelle garde son propre
  registre de ce qui a été publié et quand ;
- ensuite, la clé de signature quitte la plateforme (YubiKey ou HSM, avec un geste humain).

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
un journal intègre de chaque version entrée, de qui l'a décidée et pourquoi. Et après un avis tombé
trop tard, l'inventaire dit quels serveurs ont la version.

### La viabilité économique (20 %)

**« Combien, et qui paie ? »**
Hypothèse à tester : **300 à 800 € par mois**. Le CTO décide ; le lead dev ou le DevOps utilise ;
l'infogérant, l'auditeur ISO et l'assureur cyber prescrivent. Les déclencheurs d'achat sont un
questionnaire d'un grand compte, un audit, un incident dans l'actualité ou une due diligence de
levée de fonds.

**« Les pressions réglementaires ? »**
NIS2 (comme fournisseur), DORA par ricochet, le Cyber Resilience Act pour qui vend un logiciel.
**Les dates et les obligations précises sont à vérifier avant de les citer** (`contexte.md` § 4) :
ne pas les avancer de mémoire devant le jury.

**« Et le matériel ? »**
Le LLM tourne sur CPU : 50 à 60 s par version (7B, mesuré sur AWS). Les versions arrivent au fil
de l'eau et attendent 3 jours : ce temps ne gêne personne. Pas de GPU nécessaire.

## 5. Les choix qu'on assume

| Choix | Ce qu'on a écarté | Pourquoi |
|---|---|---|
| L'IA n'approuve jamais | une IA qui laisse passer | une erreur d'IA ne peut qu'alerter, pas ouvrir la porte |
| Pas de déchiffrement TLS | un boîtier qui inspecte tout le trafic | il deviendrait la cible n° 1 ; le relais d'API ne voit que le nom du site |
| La plateforme pousse, la passerelle ne tire rien | une passerelle qui va chercher | une passerelle compromise ne peut rien tirer d'Internet |
| Signature Ed25519 de chaque publication | la confiance dans le seul lien chiffré | une plateforme usurpée ne publie pas |
| Tout local (LLM, RAG, sandbox) | une IA dans le cloud | rien du client ne sort ; seuls des noms de paquets et des versions partent vers Internet |

## 6. Les limites, dites avant qu'on nous les montre

- **pip seulement.** npm (Verdaccio sans source amont) est conçu mais pas construit : coupé de la
  démo le 2026-10-11. Le parcours est le même ; seul le dépôt de la passerelle change.
- **Pas de WireGuard.** La démo est sur un réseau local (AWS) ; le mode hors site vient ensuite.
- **Pas de voie d'urgence** pour un correctif critique (§ 4).
- **Fin du journal non ancrée** : effacer les dernières entrées n'est pas détecté (§ 4).
- **Une plateforme réellement prise peut signer** : clé matérielle dans la version suivante.
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
4. L'ancrage du journal sur la passerelle ; une voie d'urgence tracée.
5. Une console multi-clients pour les infogérants, et une télémétrie partagée entre clients (une
   version libérée après avoir été vue saine ailleurs).

Premiers clients visés : des startups qui reçoivent des questionnaires de sécurité de grands
comptes, par leurs infogérants et leurs auditeurs ISO.
