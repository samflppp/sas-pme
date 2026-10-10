# Exigences — sas-pme

## Introduction

Sas local pour PME et startups qui développent en Python. Il filtre les paquets PyPI par une
quarantaine active (analyse du paquet + veille sur Internet) et observe les connexions sortantes des
postes pour relier un comportement suspect au paquet qui l'a causé. Le code décide ; un LLM local
alerte et explique en français.

## Exigence 1 — Index PyPI filtré

**User story :** en tant que développeur de la PME, je veux installer mes paquets comme d'habitude,
pour ne rien changer à mon travail.

1. WHEN un client demande `/simple/<paquet>/` THE SYSTEM SHALL renvoyer la page de l'index amont
   privée de toute version qui n'est pas à l'état « approuvée » ou « voie rapide ».
2. WHEN un client demande un fichier d'une version approuvée THE SYSTEM SHALL le servir depuis son
   cache, ou le télécharger de l'amont puis le servir, et vérifier son hash SHA-256 contre la page
   amont.
3. WHEN un client demande un fichier d'une version non approuvée THE SYSTEM SHALL répondre 404 et
   journaliser la demande.
4. WHEN une page `/simple/` amont contient une version inconnue du sas THE SYSTEM SHALL l'enregistrer
   à l'état « en quarantaine » avec l'heure de découverte, sans retarder la réponse.
5. THE SYSTEM SHALL répondre à `pip install` sans jamais attendre une analyse ni une veille.
6. WHEN l'amont est injoignable THE SYSTEM SHALL servir les versions approuvées déjà en cache et
   refuser toute version nouvelle (fail-closed).
7. WHEN un paquet est demandé pour la première fois et qu'aucune de ses versions n'est approuvée THE
   SYSTEM SHALL approuver d'office la version la plus récente publiée depuis plus de 48 h dont les
   étages 1 et 2 ne lèvent aucun signal, et journaliser cette « adoption initiale ».

## Exigence 2 — Quarantaine active

**User story :** en tant que responsable technique, je veux qu'aucune version neuve n'atteigne un poste
avant d'avoir été vérifiée, pour ne pas être la victime des premières heures.

1. THE SYSTEM SHALL garder une version en quarantaine au moins pendant un délai configurable, 48 h
   par défaut, compté depuis sa date de publication sur PyPI.
2. WHEN le délai est écoulé et qu'aucun signal n'est levé THE SYSTEM SHALL passer la version à
   « approuvée ».
3. WHEN une version corrige une vulnérabilité critique connue d'OSV de la version approuvée courante
   et que les étages 1 et 2 ne lèvent aucun signal THE SYSTEM SHALL la passer à « voie rapide » sans
   attendre le délai ; le LLM la lit ensuite en différé.
4. WHEN une personne approuve ou bloque une version à la main THE SYSTEM SHALL appliquer la décision et
   la journaliser avec son auteur et sa raison.

## Exigence 3 — Étage 1 : contrôles déterministes

1. THE SYSTEM SHALL calculer pour chaque version en quarantaine : distance de nom aux 5 000 paquets les
   plus téléchargés, âge du paquet, changement de comptes de publication par rapport à la version
   précédente, présence dans OSV, présence dans OpenSSF malicious-packages, statut « yanked »,
   livraison sans wheel avec `setup.py`.
2. WHEN un paquet figure dans OpenSSF malicious-packages ou qu'une version est retirée par PyPI pour
   malveillance THE SYSTEM SHALL lever un signal « bloque ».
3. WHEN la distance de nom à un paquet populaire est de 1 ou 2 éditions et que le nom diffère THE
   SYSTEM SHALL lever un signal « fort » de typosquat.

## Exigence 4 — Étage 2 : diff entre versions

1. THE SYSTEM SHALL extraire l'archive de la version et celle de la version approuvée précédente, et
   produire la liste des fichiers ajoutés ou modifiés.
2. THE SYSTEM SHALL rechercher dans les seules parties ajoutées : code exécuté à l'installation ou à
   l'import (`setup.py`, `__init__.py`, fichiers `.pth`), appels `exec`, `eval`, `compile`,
   `subprocess`, `os.system`, `base64.b64decode`, `marshal`, domaines ou IP en dur, lecture de
   `~/.ssh`, `~/.aws`, `.env` ou de variables d'environnement contenant `TOKEN`, `KEY` ou `SECRET`,
   blocs binaires ou de haute entropie.
3. THE SYSTEM SHALL produire chaque constat avec fichier, ligne et extrait de 200 caractères au plus.

## Exigence 5 — Étage 3 : LLM local de verdict

1. THE SYSTEM SHALL envoyer au LLM local les constats, les extraits, le changelog et les articles de
   veille, encadrés comme données à juger.
2. THE SYSTEM SHALL exiger une réponse JSON conforme au schéma `signaux[]`, `incoherence_changelog`,
   `explication` ; WHEN la réponse n'est pas conforme THE SYSTEM SHALL l'ignorer et le journaliser.
3. THE SYSTEM SHALL ne retenir du LLM que des signaux qui montent le risque ; aucune sortie du LLM ne
   peut lever un signal du code ni approuver une version.
4. WHEN le LLM est indisponible THE SYSTEM SHALL laisser la version en quarantaine au-delà du délai et
   l'afficher « à revoir ».

## Exigence 6 — Veille sur Internet

**User story :** en tant que responsable technique, je veux savoir si les chercheurs ou la presse ont
dénoncé une version, pour profiter de ce que le monde sait avant moi.

1. WHILE une version est en quarantaine THE SYSTEM SHALL interroger toutes les 2 h OSV.dev, le statut
   PyPI de la version et les flux RSS configurés.
2. THE SYSTEM SHALL n'envoyer à l'extérieur que le nom du paquet et la version.
3. WHEN une source structurée (OSV, yanked, OpenSSF) signale la version THE SYSTEM SHALL lever un
   signal « bloque ».
4. WHEN un article d'une source libre mentionne le paquet THE SYSTEM SHALL le faire classer par le LLM
   local (danger oui/non, extrait) ; WHEN le LLM y voit un danger THE SYSTEM SHALL passer la version à
   « à revoir », jamais à « bloquée » sur cette seule base.
5. THE SYSTEM SHALL ne jamais abaisser un risque sur la foi d'un article.
6. WHEN un signal de veille arrive sur une version déjà approuvée THE SYSTEM SHALL la repasser à
   « bloquée » ou « à revoir » et lister les postes qui l'ont installée.

## Exigence 7 — Proxy des sorties et agent des sorties

**User story :** en tant que responsable technique, je veux voir quand un poste contacte un endroit
anormal, pour rattraper ce que la première barrière a laissé passer.

1. THE SYSTEM SHALL relayer les requêtes `CONNECT` sans déchiffrer le TLS, et journaliser poste,
   domaine, port, heure, octets envoyés et reçus, durée.
2. THE SYSTEM SHALL lever les signaux : domaine jamais vu dans la PME, domaine créé depuis moins de
   30 jours (RDAP), IP brute, connexions régulières à intervalle stable (battement).
3. WHEN un domaine jamais vu apparaît sur un poste dans les 10 minutes qui suivent l'installation d'une
   version par ce poste THE SYSTEM SHALL lever un signal « bloque » de corrélation sur cette version,
   bloquer le domaine pour toute la PME et lister les autres postes qui ont installé la version.
4. WHERE un poste est déclaré « CI » THE SYSTEM SHALL n'autoriser que les domaines de sa liste fermée
   et bloquer le reste.
5. THE SYSTEM SHALL faire résumer toutes les 15 minutes par le LLM local les signaux regroupés par poste
   en alertes en français ; le LLM ne peut effacer aucun signal.

## Exigence 8 — Console

1. THE SYSTEM SHALL afficher : nombre de versions en quarantaine, bloquées sur 7 jours, alertes de
   sortie ouvertes ; un fil des décisions ; une fiche par version ; une fiche par poste ; le journal.
2. THE SYSTEM SHALL permettre d'approuver ou de bloquer une version et de clore une alerte en un clic.
3. THE SYSTEM SHALL présenter chaque décision par une phrase en français suivie de ses preuves.

## Exigence 9 — Journal

1. THE SYSTEM SHALL écrire chaque décision, automatique ou humaine, dans un journal append-only
   horodaté, chaque entrée chaînée par le hash de la précédente.
2. THE SYSTEM SHALL vérifier la chaîne à la demande et signaler toute rupture.

## Exigence 10 — Mesure

**User story :** en tant que porteur, je veux un chiffre de détection et de fausses alertes, pour
prouver l'efficacité devant le jury.

1. THE SYSTEM SHALL fournir un script qui rejoue un corpus d'environ 30 versions malveillantes (OpenSSF
   malicious-packages) et 50 mises à jour saines de paquets populaires.
2. THE SYSTEM SHALL afficher, pour trois configurations — étage 1 seul ; étages 1+2+3 ; étages 1+2+3 +
   veille —, le taux de détection et le taux de fausses alertes.

## Hors périmètre (PoC)

npm, winget, mises à jour d'OS, comparaison au tag git, bac à sable d'exécution, second LLM
relecteur, envoi anormal, noms générés, heures anormales, multi-sites, console d'infogérant,
authentification de la console, haute disponibilité.
