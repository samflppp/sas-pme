# Roadmap du MVP

**But :** une démo qui est un vrai MVP, avec une base commune très tôt pour que les trois travaillent sur
le même fil, et non dans le vide.

**Règle :** chaque jalon se termine par un **point de rencontre** où le tout marche de bout en bout.
Si une partie a fini avant les autres, elle prend une tâche « en attendant » de sa colonne, prévue
d'avance, et n'avance pas sur le jalon suivant.

H0 = début de la roadmap. Le budget est d'environ 30 h, dont 6 de marge et de sommeil en quinconce.

## M0 — Socle commun (H0 → H3)

**But :** le squelette de bout en bout, avec des faux partout où il le faut.

| A — Sam | B — Mouabd19 | C — STEUSSO |
|---|---|---|
| `commun/modeles.py` (contrats de `contrats.md`) poussé **avant H1** ; `pyproject.toml` ; `plateforme/db` (schéma SQLite + accès) ; web : page de connexion fixe et catalogue vide | `plateforme/pipeline` : client PyPI (métadonnées, téléchargement) ; `demander()` qui enregistre une version ; politique factice « tout approuver » | AWS : VPC, sous-réseau public (plateforme), **sous-réseau privé sans Internet** (passerelle + serveur) ; pypiserver sur la passerelle ; stubs `sandbox.executer` et `signature.publier` (copie des archives par `scp`) |

**Point H3, la preuve de vie :** atteint le 2026-10-10 (`docs/points/2026-10-10-C-h3-ok.md`).
1. une personne demande `requests` dans l'interface web ;
2. la version est téléchargée, approuvée et copiée sur la passerelle ;
3. sur le serveur, `pip install requests` marche, alors que `curl https://pypi.org` échoue.

**En attendant :**
- A : maquette des pages ;
- B : corpus de test (30 versions malveillantes OpenSSF, 50 saines) ;
- C : quota GPU, installation d'Ollama et des modèles.

## M1 — MVP démontrable, pip (H3 → H10)

| A — Sam | B — Mouabd19 | C — STEUSSO |
|---|---|---|
| Comptes et rôles (admin, dev), sessions ; catalogue des versions publiées ; **fiche d'une version** (verdict, signaux, preuves, rapport de sandbox) ; **file d'attente** avec compte à rebours ; page « demander un paquet » ; journal chaîné par hash | **délai de 3 jours** (réglable en démo) ; veille OSV + statut PyPI ; **analyse statique** (typosquat, âge, mainteneurs, OpenSSF, diff avec la version précédente : code à l'installation, `exec`/`base64`, secrets, domaines) ; **LLM local** (verdict JSON, phrase en français, confiné) ; **politique** déterministe | **récepteur de la passerelle** (`/v1/publish`, `/v1/revoke`, `/v1/inventory`) ; **TLS mutuel** ; **signature Ed25519** côté plateforme et vérification côté passerelle (hash, âge, nonce) ; inventaire lu dans les journaux de pypiserver ; **sandbox v1** (conteneur sans réseau + faux DNS qui enregistre + leurres) |

**Point H10, le MVP :** atteint le 2026-10-10, M1 validé pour A, B et C (`docs/points/2026-10-10-A-m1-valide.md`).
1. une version propre attend son délai, est analysée, approuvée, signée et publiée, et le serveur
   l'installe ;
2. la version piégée de démo est **bloquée**, avec les preuves statiques, les preuves de sandbox (DNS
   vers le domaine de l'attaquant, leurre lu) et une phrase en français ;
3. une publication mal signée est **refusée** par la passerelle.

**Ce point est la démo minimale garantie.**

**En attendant :**
- A : script de démo ;
- B : mesure sur le corpus (contrôles seuls) ;
- C : durcissement de la passerelle (`ufw`, utilisateur sans droits).

## M2 — Ce qui fait la différence (H10 → H16)

| A — Sam | B — Mouabd19 | C — STEUSSO |
|---|---|---|
| Décision humaine sur une version à revoir ; **révocation** depuis l'interface ; tableau de bord (compteurs) ; page inventaire | **RAG** (OSV/GHSA, OpenSSF, CWE, CAPEC, ATT&CK ; Chroma ; références citées dans le verdict) ; le rapport de sandbox dans le prompt du LLM ; veille par flux RSS (un article ne débloque jamais) | **sandbox v2** (`strace` des fichiers lus, battement observé 60 s) ; **relais d'API** en liste fermée (serveur → passerelle → plateforme) ; **sauvegardes** (`restic`, avec un test de restauration) |

**Extensions, dans l'ordre, s'il reste du temps :**
1. **npm** : Verdaccio sans source amont (C), contrôles npm (B), affichage (A) ;
2. **WireGuard** pour le mode hors site (C).

**Point H16 :** démo complète répétée une fois. On gèle les fonctions.

## M3 — Finition (H16 → H22)

| A — Sam | B — Mouabd19 | C — STEUSSO |
|---|---|---|
| deck (8 diapositives), fiche de défense, répétition du pitch | **mesure finale** : trois colonnes, détection et fausses alertes (contrôles seuls ; + sandbox ; + LLM/RAG) + diapositive | **vidéo** de démo de 3 min au plus ; schéma réseau pour le deck ; diapositive « et si la plateforme est compromise ? » |

**Point H22 :** vidéo, deck et mesure terminés. Ensuite, H22 → H30 : marge, sommeil en quinconce,
répétitions.

## Ordre de coupe si on prend du retard

1. npm ;
2. WireGuard (le mode réseau local suffit pour la démo) ;
3. veille par flux RSS ;
4. RAG (le LLM reste, sans citations) ;
5. sandbox v2 (on garde la v1).

**On ne coupe jamais :** le cloisonnement, la signature, la sandbox v1, la mesure.

## La démo (3 minutes)

1. Sur le serveur : `curl https://pypi.org` échoue, `pip install requests` marche. *Le serveur ne
   parle jamais à Internet.*
2. Interface web : la nouvelle version de `requests` attend ses 3 jours, puis devient approuvée,
   signée et publiée. Le serveur la reçoit avec `pip install -U`.
3. Une version piégée sort. Elle est bloquée avec ses preuves : la sandbox l'a vue appeler son serveur
   et lire un faux jeton. Le LLM l'explique en citant un cas connu du RAG. *Le serveur ne la verra
   jamais.*
4. Une publication forgée, sans la bonne signature, est refusée par la passerelle. *Même la
   plateforme usurpée ne peut rien publier.*
5. Diapositive de mesure.
