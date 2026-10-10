# Point B (Mouabd19) — relecture du code de A et de C jusqu'au M1 — 2026-10-10

## Fait
- J'ai relu en lecture seule le code de A (`plateforme/web/`, `plateforme/db/`, `commun/`) et celui
  de C (`plateforme/sandbox/`, `plateforme/signature/`, `passerelle/`, `infra/`).
- **Je n'ai rien modifié chez vous.** Vos tests passent tous : 103 chez A, 85 chez C (2 sautés).
- Chaque constat a été vérifié dans le code. Ceux marqués « reproduit » ont été confirmés par un
  petit script, hors du dépôt, sans Docker et sans AWS.
- **Priorité H16 :** les constats C1, C2, C3 et A1. Ils touchent une promesse que la démo fait au
  jury.

## Ce qui est solide
- **A :**
  - les rôles sont relus en base à chaque requête ;
  - les requêtes SQL sont paramétrées partout ;
  - l'échappement automatique est actif et aucun `|safe` n'est utilisé ;
  - les mots de passe sont en empreinte scrypt salée, avec `compare_digest` et une empreinte
    leurre ;
  - seul un humain approuve (`HUMAIN`).
- **C :**
  - la signature est vérifiée sur les octets bruts reçus ;
  - les fichiers reçus doivent correspondre exactement au manifeste ;
  - le nonce n'est consommé qu'après un succès complet ;
  - le TLS mutuel est exigé ;
  - les options Docker suivent l'architecture § 5 ;
  - aucun secret dans Git, ni dans l'historique.

## Demandes à C (STEUSSO)
| # | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C1 | **La sandbox peut être rendue aveugle (reproduit).** `_lire` (`plateforme/sandbox/__init__.py:68`, appelé l. 147) ne lit que les 5 premiers Mo de `reseau.jsonl`. Un paquet envoie environ 110 000 requêtes DNS `localhost` au piège, puis fait sa vraie fuite. Le rapport revient alors avec `requetes_dns=[]`, `connexions=[]` et `leurres_lus=[]`. Correctif : lire tout le fichier en ne gardant que les lignes utiles, ou faire ignorer et dédoublonner les noms locaux par le piège lui-même ; et compter un journal tronqué comme un signal suspect. | H16 (preuve de la démo) | ok / question |
| C2 | **Le paquet peut effacer ses traces.** `/journal` est monté en écriture dans la cible (l. 53, mode 0777 l. 112). Le paquet peut faire `os.truncate("/journal/trace.jsonl", 0)` et écrire `0` dans `code_import`. Les fichiers lus, les leurres lus et le code de sortie disparaissent alors. Correctif avant `strace` (v2) : traiter un `trace.jsonl` vide ou incohérent comme suspect, par exemple en exigeant un événement de début et un de fin écrits par `lancer.sh`. | H16 | ok / question |
| C3 | **Une publication peut passer sans signature.** Sans `SAS_PASSERELLE_URL`, `publier` copie par scp sans signer et sans avertir (`plateforme/signature/__init__.py:37`, 90). De plus, la clé SSH n'a pas de phrase de passe (`infra/aws/installer.sh:19`), le dépôt appartient à `ubuntu:pypi` (l. 43) et le port 22 est ouvert depuis la plateforme (l. 106). Avec cette clé, on écrit dans le dépôt sans signature. Correctif : retirer le stub M0, ou au moins le refuser hors d'une variable explicite de test ; réserver l'écriture du dépôt au seul `recepteur`. | H16 (« rien n'est publié sans signature ») | ok / question |
| C4 | **Une révocation peut répondre 200 sans rien retirer** (déjà dans `B-reponse-inventaire`). `/v1/revoke` ne remplace que `-` par `_`, donc il rate `zope.interface-6.0.tar.gz`. Correctif : la règle de l'inventaire (`parse_wheel_filename` / `parse_sdist_filename`), et 404 si rien n'est retiré. | — | ok / non |
| C5 | **Le DNS sort probablement du sous-réseau privé.** Le résolveur d'AWS (VPC+2) n'est pas filtré par les groupes de sécurité. Sur le serveur, `dig exemple.com` : s'il répond, un paquet peut faire fuir des données par DNS. Correctif : `aws ec2 modify-vpc-attribute --no-enable-dns-support` (les noms sont déjà dans `/etc/hosts`). Je n'ai pas pu tester d'ici. | démo du cloisonnement | sortie de `dig` |
| C6 | **Le compte `pypi` peut écrire `nonces.txt` et `registre.txt`** (`infra/passerelle/pypiserver.service:29`, `installer.sh:38`). Un pypiserver compromis peut vider les nonces et rejouer un manifeste capté, ou fausser l'inventaire. Correctif : mettre ces fichiers dans un dossier réservé au seul `recepteur`. | — | ok / non |
| C7 | **Mineurs :** dans `rapport.py`, placer les connexions vues par le piège **avant** celles du traceur, que le paquet contrôle et peut remplir jusqu'au plafond de 100 ; ouvrir les journaux avec `O_NOFOLLOW`, car un lien symbolique posé par le paquet est aujourd'hui suivi ; attendre 60 s au lieu de 10 (prévu en v2). | — | ok |

## Demandes à A (Sam)
| # | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| A1 | **Le journal chaîné ne détecte pas une réécriture (reproduit).** `_hash` (`plateforme/db/acces.py:91`) est un sha256 sans clé, et la tête de la chaîne n'est fixée nulle part hors de la base. Quelqu'un qui a la main sur la base peut faire `DROP TRIGGER`, puis supprimer les dernières entrées, ou réécrire « bloquée » en « approuvée » et recalculer la chaîne. `verifier_journal()` rend alors `(True, None)`. Correctif : un HMAC avec une clé hors de la base (variable d'environnement), ou ancrer le dernier hash ailleurs (dans le manifeste signé envoyé à la passerelle). Sinon, corriger la phrase de `contrats.md` § 2 et ne pas faire cette promesse au jury. | H16 (« le journal ne s'efface pas ») | ok / question |
| A2 | **`enregistrer_inventaire` peut laisser la base bloquée (reproduit).** `BEGIN` / `COMMIT` n'ont pas de `ROLLBACK` (l. 211). Deux entrées en double lèvent une erreur, et la transaction reste ouverte. Les écritures suivantes, journal compris, ne sont alors jamais validées. Correctif : `with self._c:` ou `try/except: ROLLBACK`. À faire avant la page inventaire du M2. | page inventaire (M2) | ok |
| A3 | **Deux `Base` sur le même fichier cassent la chaîne (reproduit).** Le verrou est propre à chaque instance (`_journaliser`, l. 355). Avec `uvicorn --workers 2`, ou un script lancé pendant que le web tourne, `verifier_journal()` signale une fausse falsification. Correctif : lire le dernier hash puis faire l'`INSERT` dans un même `BEGIN IMMEDIATE`. | — | ok |
| A4 | **Deux décisions humaines simultanées s'écrasent.** L'`UPDATE` de `changer_etat` (l. 153) ne vérifie pas l'état de départ, et le journal est écrit dans une autre transaction. Un « approuver » peut donc écraser un « bloquer » arrivé quelques millisecondes plus tôt. Correctif : ajouter `AND etat=?` (l'état attendu) et faire l'UPDATE et le journal dans la même transaction. | — | ok |
| A5 | **Mineurs :** pas de jeton CSRF sur les POST (`same_site="strict"` ne distingue pas les ports de `localhost`, or la démo passe par un tunnel) : vérifier au moins l'en-tête `Origin` ; changer son mot de passe ne coupe pas les sessions déjà ouvertes ; `SAS_ADMIN_MOTDEPASSE` n'est pas soumis à `MDP_MIN` (`app.py:441`). | — | ok |

## Ensuite
- Je relirai vos correctifs si vous voulez. Mon M2 attend toujours la validation sur AWS (point
  `B-rag-qualite`).
