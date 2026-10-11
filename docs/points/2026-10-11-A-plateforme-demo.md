# Point A (Sam) — la plateforme comme scène unique de la démo — 2026-10-11

Décision de Sam : pendant la démo, on ne quitte jamais la plateforme. Conception :
`docs/conception-demo.md`. Sam a demandé que A fasse tout, **y compris dans les dossiers de B et
de C** : ce point le leur signale, fichier par fichier.

## Fait (5 PR empilées, à fusionner dans l'ordre)
1. **#90, gabarit** : barre latérale à la Power BI, styles et polices de pipelad.tech servis par
   `/statique`, états lisibles (« en attente », « à revoir »).
2. **#91, catalogue** : arborescence à la GitHub (`pypi/`, `npm/`, `images/` → paquet → versions
   → fichiers). Une version montre ses archives (taille, sha256) et ses données (verdict, rapport de
   sandbox, signaux), ouvertes comme un fichier. Images Docker : liste tenue à la main
   (`plateforme/web/images-agreees.json`, vrais digests), dite « non analysée par la pipeline ».
3. **#92, étapes en direct (dossier de B)** : `traiter(..., suivi=rappel)` dit chaque étape
   (téléchargement, sandbox, statique, IA, politique, publication) ; fins et erreurs vont au journal
   chaîné (action `etape`). `llm.analyser(..., morceau=f)` lit Ollama en flux. Sans `suivi` ni
   `morceau`, rien ne change : tous les tests de B passent tels quels.
4. **#94, pages Demandes et Direct** : une demande journalise sa résolution (`demande_resolue` :
   la version demandée puis ses dépendances) et ouvre `/direct`, qui suit chaque version en direct
   (Server-Sent Events), l'explication de l'IA mot à mot.
5. **Cette PR, panneau Serveur (dossier de C)** :
   - plateforme : une demande envoie aussi au serveur une **demande d'installation signée**
     (`signature.demander_installation`, Ed25519, octets préfixés : une signature de manifeste ne
     vaut jamais demande d'installation) ;
   - passerelle : `POST /v1/install` (TLS mutuel, même clé, âge, nonce) range la demande ;
     `GET /v1/access` rend les lignes du journal de pypiserver ; **guichet** `passerelle.guichet`
     sur :8444, en lecture seule, rend les demandes aux serveurs ;
   - serveur : **agent** `infra/serveur/agent_installation.py`, qui revérifie la signature, l'âge,
     le nonce (une fois, même après redémarrage) et le nom (jamais une option de pip), puis lance
     `pip install --upgrade <nom>` vers la passerelle seulement ;
   - le panneau Serveur affiche les **vraies** lignes du journal d'accès depuis la demande, la
     version reçue (« la dernière version vérifiée ») et la version amont qui n'est pas servie.

Vérifié en local de bout en bout (faux PyPI de B, passerelle mTLS, guichet, pypiserver, faux
Ollama en flux, agent dans un venv à part) : `demo-horodatage` demandé → le serveur installe 1.0,
la 1.1 sortie sur PyPI reste « en attente », la pipeline analyse et publie sous les yeux.
Suite complète : 579 verts. Chaque test neuf a été vu rouge, ou le code cassé une fois.

## Pour C (STEUSSO) : ce qui change dans tes dossiers
- `passerelle/installation.py`, `passerelle/acces.py`, `passerelle/guichet.py` (neufs) ;
  `passerelle/recepteur.py` : `/v1/access`, `/v1/install`, paramètre `installations`.
- `plateforme/signature/__init__.py` : `demander_installation`, `lire_acces`.
- `infra/passerelle/guichet.service` (neuf), `recepteur.service` (`SAS_INSTALLATIONS`).
- `infra/serveur/agent_installation.py`, `agent-installation.service` (neufs) : l'agent tourne
  sous `ubuntu` avec le Python du système (qui doit avoir `cryptography` : vérifié par le script) et
  installe dans le venv `~/app`.
- `infra/aws/creer.sh` : port 8444 du serveur vers la passerelle. `installer.sh` : guichet à
  l'étape 7, ufw 8444 à l'étape 8, agent à l'étape 11 bis.

## Pour B (Mouabd19) : ce qui change dans ton dossier
- `plateforme/pipeline/suivi.py` (neuf) ; `traitement.py` : paramètre `suivi`, étapes ;
  `llm.py` : paramètre `morceau`, lecture en flux. Rien ne change sans eux.

## Script de démo
`demo/script.md`, nouvelle section « Démo dans la plateforme » : le parcours Demandes → Direct →
Catalogue en 2 minutes, et quoi faire si quelque chose casse.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Relire #95, surtout `/v1/install`, le guichet et l'agent ; au redéploiement, `creer.sh` (règle 8444) puis `installer.sh` | démo | ok / remarques |
| C (STEUSSO) | Sur le serveur AWS : `python3 -c "import cryptography"` passe-t-il ? | démo | oui / non |
| C (STEUSSO) | Relancer `infra/aws/domaine.sh` pour la nouvelle vitrine (#87, et #96 si fusionnée) | vitrine | fait |
| B (Mouabd19) | Relire #92 (`suivi`, LLM en flux) | démo | ok / remarques |
