# Architecture

## 1. Les zones

```
                         INTERNET
                            │  pypi.org, registry.npmjs.org, api.osv.dev, flux RSS, API autorisées
┌───────────────────────────▼───────────────────────────┐
│ PLATEFORME AGRÉÉE                 (sur site ou hors site) │
│  web :443 ── interface « GitHub local », comptes        │
│  pipeline ── veille → délai 3 j → statique → sandbox    │
│              → LLM + RAG → politique → signature        │
│  ollama :11434 (local)   chroma (local)   sqlite         │
│  relais API :3129 (liste fermée)                        │
└───────────────┬───────────────────────────────────────┘
                │ LIEN UNIQUE : LAN, ou WireGuard si hors site
                │ TLS mutuel ; manifestes signés Ed25519
                │ plateforme → passerelle : publier, révoquer, lire l'inventaire
                │ passerelle → plateforme : relais API seulement
┌───────────────▼───────────────────────────────────────┐
│ PASSERELLE « BOÎTE NOIRE »        (sur site, sans Internet) │
│  récepteur :8443 ── vérifie signature + hash, publie    │
│  pypiserver :8080/simple   verdaccio :4873 (sans amont) │
│  inventaire (journaux de téléchargement)                │
│  relais API :3128 → plateforme :3129                    │
└───────────────┬───────────────────────────────────────┘
                │ pip / npm / API, réseau local seulement
┌───────────────▼───────────────────────────────────────┐
│ SERVEURS SENSIBLES                (sans Internet)         │
│  pip index-url = http://passerelle:8080/simple          │
│  npm registry  = http://passerelle:4873                 │
│  HTTPS_PROXY   = http://passerelle:3128 (API autorisées) │
└───────────────────────────────────────────────────────┘
```

## 2. Les composants

| Composant | Où | Logiciels | Propriétaire |
|---|---|---|---|
| Interface web + API interne | plateforme | Python 3.12, FastAPI, Jinja2 + HTMX, SQLite | A |
| Pipeline (veille, délai, statique, LLM, RAG, politique) | plateforme | Python, httpx, rapidfuzz, Ollama (`qwen2.5-coder:7b`, `nomic-embed-text`), Chroma | B |
| Sandbox | plateforme | Docker, conteneur sans réseau, faux DNS/HTTP qui enregistre, `strace` | C |
| Signature | plateforme (signe) + passerelle (vérifie) | `cryptography` (Ed25519) | C |
| Récepteur, dépôts, inventaire, relais d'API | passerelle | FastAPI, pypiserver, Verdaccio, relais CONNECT asyncio | C |
| Réseau | AWS | VPC, sous-réseau public (plateforme), sous-réseau privé sans route Internet (passerelle, serveur), groupes de sécurité, WireGuard | C |

## 3. Les flux

| # | De → vers | Protocole | Contenu |
|---|---|---|---|
| 1 | plateforme → Internet | HTTPS | métadonnées et archives publiques de PyPI/npm ; nom + version vers OSV ; flux RSS |
| 2 | plateforme → passerelle | HTTPS + TLS mutuel | `POST /v1/publish` (manifeste signé + archives), `POST /v1/revoke`, `GET /v1/inventory` |
| 3 | serveur → passerelle | HTTP (réseau local) | `pip`/`npm` : pages d'index et archives des seules versions publiées |
| 4 | serveur → passerelle → plateforme → Internet | CONNECT, sans déchiffrement | appels d'API vers des domaines en liste fermée, journalisés |
| 5 | navigateur → plateforme | HTTPS | interface web, après connexion |
| 6 | pipeline → Ollama, Chroma | local | extraits ≤ 200 caractères, constats, rapport de sandbox, passages du RAG ; réponse JSON validée |

**Ce qui ne quitte jamais la PME :** le code et les données des serveurs, l'inventaire, les verdicts.
**Ce qui sort vers Internet :** des noms de paquets avec leurs versions, des téléchargements publics,
et les appels d'API explicitement autorisés.

## 4. Les états d'une version

```
nouvelle ─▶ en_attente (3 jours, veille active) ─▶ en_analyse ─┬─▶ approuvée ─▶ publiée
                     │                                          ├─▶ à_revoir ──(humain)──▶ approuvée | bloquée
                     └── signal bloquant de la veille ──────────┴─▶ bloquée
publiée ── signal tardif ──▶ révoquée (retirée de la passerelle)
```

## 5. La sandbox (détail)

- **Le conteneur :**
  - image `python:3.12-slim` ou `node:20-slim` ;
  - `--network` sur un réseau Docker **interne**, sans sortie, où ne se trouve qu'un **faux DNS et faux
    HTTP** qui répondent à tout et enregistrent chaque requête ;
  - `--read-only` sauf `/tmp`, `--cap-drop ALL`, `--pids-limit 256`, `--memory 1g`, durée maximale
    120 s.
- **Le scénario :**
  1. installer l'archive (`pip install --no-deps <fichier>` ou `npm install <tgz>`) ;
  2. importer ou `require` le module ;
  3. attendre 60 s pour attraper un battement.
- **Les leurres :** de fausses variables `AWS_SECRET_ACCESS_KEY`, `GITHUB_TOKEN` et `NPM_TOKEN`, et de
  faux fichiers `~/.aws/credentials`, `~/.ssh/id_rsa` et `~/.npmrc`.
- **Le rapport (`SandboxReport`) :**
  - les requêtes DNS ;
  - les connexions tentées ;
  - les fichiers sensibles lus (`strace -e trace=openat`) ;
  - les processus lancés ;
  - la lecture des leurres ;
  - le code de sortie et la durée.

## 6. Le RAG

- **Sources, téléchargées sur la plateforme et indexées une fois :**
  - les avis OSV et GHSA des écosystèmes PyPI et npm ;
  - OpenSSF malicious-packages ;
  - CWE, CAPEC, et les techniques MITRE ATT&CK de la chaîne d'approvisionnement ;
  - une sélection de rapports de chercheurs.
- **Index :** Chroma persistant. Les embeddings sont calculés par Ollama avec `nomic-embed-text`.
- **Usage :** les constats et le rapport de sandbox servent de requête. Les 5 meilleurs passages sont
  donnés au LLM comme **données**. Le verdict cite leurs identifiants (`MAL-2024-…`, `CWE-506`…).

## 7. La démo sur AWS

- **Région :** `eu-west-3`. **Un VPC, deux sous-réseaux :**
  - public : la plateforme, sur `g4dn.xlarge` (GPU T4), avec IP publique ;
  - **privé, sans passerelle NAT ni route vers Internet** : la passerelle (`t3.small`) et un serveur
    sensible (`t3.small`).
- **Groupes de sécurité :**
  - passerelle : 8443 depuis la plateforme seulement ; 8080, 4873 et 3128 depuis le serveur seulement ;
  - serveur : SSH par un bastion (la plateforme), rien d'autre.
- **Mode « hors site » :** WireGuard entre la plateforme et la passerelle (UDP 51820). C'est une
  extension (M2).
- **Repli si le quota GPU vaut 0 :** `c7i.4xlarge` (CPU) avec `qwen2.5-coder:3b`.
- **Mode démo :** délai réglable à quelques minutes, et une **source amont de démo** (pypiserver sur la
  plateforme) qui publie des versions avec des dates contrôlées.

## 8. Le dépôt

```
sas-pme/
├── CLAUDE.md                 # lu à chaque prompt par Claude Code
├── .kiro/steering/           # lu à chaque prompt par Kiro
├── docs/                     # contexte, architecture, contrats, roadmap, organisation, sauvegardes
├── commun/                   # contrats partagés (schémas pydantic, états) — tâche M0, changements par PR à 3
├── plateforme/
│   ├── web/                  # A
│   ├── db/                   # A (schéma + accès)
│   ├── pipeline/             # B (veille, délai, statique, llm, rag, politique)
│   ├── sandbox/              # C
│   └── signature/            # C (signer)
├── passerelle/               # C (récepteur, vérification, pypiserver, verdaccio, inventaire, relais)
├── infra/                    # C (AWS, WireGuard, sauvegardes)
├── demo/                     # A script ; B paquets piégés et corpus ; C réseau de démo
├── mesure/                   # B
└── tests/                    # miroir des dossiers ci-dessus
```
