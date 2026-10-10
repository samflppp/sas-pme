# Point B (Mouabd19) — M1 : analyse statique du code et des métadonnées — 2026-10-10

## Fait
- **`statique/code.py`** : les archives sont lues **en mémoire**, jamais extraites ni exécutées.
  - Aucun lien suivi, des tailles plafonnées contre les bombes de décompression.
  - Les tests du paquet ne sont pas lus.

  Les constats sont placés là où le code s'exécute tout seul : `setup.py`, `.pth`,
  `__init__.py` de premier niveau.

  | Sorte | Niveau | Quoi |
  |---|---|---|
  | `exfiltration` | **BLOQUANT** | au même point d'exécution : lecture d'un secret **et** appel réseau |
  | `code_installation` | FORT | `setup.py` ou `.pth` qui lance une commande, ouvre le réseau ou fait `exec` |
  | `exec_obfusque` | FORT | `exec`/`eval` d'un contenu décodé (base64, zlib, marshal…), partout |
  | `acces_secrets` | FORT | `~/.aws/credentials`, `~/.ssh/id_*`, `GITHUB_TOKEN`… au point d'exécution |
  | `domaine_suspect` | FORT | service d'exfiltration (webhook Discord, ngrok, pastebin…) ou IP publique brute, partout |
  | `archive_illisible` | FORT | archive corrompue |
  | `setup_personnalise`, `pth_import`, `bloc_base64`, `fichier_ignore` | MOYEN | indices, ne bloquent pas |
  | `domaine` | INFO | domaines cités au point d'exécution |

- **Diff** : si les archives de la version publiée précédente sont là, seul le **nouveau** compte
  (`preuve["nouveau"]`).
- **`statique/meta.py`** :
  - `projet_recent` (projet de moins de 30 jours) ;
  - `mainteneur_change` (aucun courriel d'auteur ou de mainteneur en commun avec la version
    précédente).

  Les deux sont des indices, de niveau MOYEN. PyPI injoignable → aucun signal.
- **OpenSSF** : déjà couvert par la veille. OSV importe la base OpenSSF malicious-packages
  (identifiants `MAL-…`).
- `traiter()` réunit ces signaux avec ceux du nom, puis la politique décide. Les preuves (`fichier`,
  `ligne`, `extrait` ≤ 200 caractères) arrivent sur la fiche de A.
- **Fausses alertes mesurées** sur 20 paquets populaires sains, lus seulement, jamais installés
  (requests, botocore, django, numpy, setuptools, awscli…) : **0 signal FORT ni BLOQUANT**, 4 MOYEN.
  Ces paquets ont servi à régler les règles : il faudra une mesure sur le corpus à part.
- 255 tests passent. Le code a été cassé neuf fois pour voir les tests au rouge.

## Disponible pour vous
- **A :** nouvelles sortes de signaux avec `preuve["fichier"]`, `["ligne"]`, `["extrait"]`, et
  `["domaine"]` ou `["nouveau"]` selon la sorte.

## Limites connues
- Seules les archives déjà sur la plateforme servent au diff : pas de téléchargement de la version
  précédente.
- Règles par expressions régulières : un code très obfusqué peut passer. C'est le rôle de la
  sandbox et du LLM.

## Ensuite
- Rapport de sandbox → signaux, LLM local, paquets de démo.
