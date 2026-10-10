# Architecture — sas-pme

## Les machines

| Machine | Rôle dans la démo | Rôle dans le produit |
|---|---|---|
| EC2 `g4dn.xlarge` (GPU NVIDIA T4, 4 vCPU, 16 Go) | le boîtier du sas | un mini-PC ou une VM dans le placard de la PME |
| PC d'un membre de l'équipe | un poste de développeur | chaque poste et serveur de CI de la PME |
| pypi.org, api.osv.dev, rdap.org, flux RSS | Internet | Internet |

## Les logiciels sur le boîtier

| Logiciel | Version | Rôle | Écoute |
|---|---|---|---|
| Ubuntu 22.04 (AMI Deep Learning Base, pilote NVIDIA) | — | système | — |
| Python | 3.12 | tout le sas | — |
| FastAPI + uvicorn | 0.115 / 0.30 | index PyPI filtré + console | `0.0.0.0:8080` |
| Proxy CONNECT maison (`asyncio`) | — | relais des sorties sans déchiffrement | `0.0.0.0:3128` |
| Ollama + `qwen2.5-coder:7b` | 0.3+ | LLM local (verdicts, articles, résumés) | `127.0.0.1:11434` |
| SQLite | 3.x | état, signaux, flux, journal chaîné | fichier `sas.db` |
| pypiserver | 2.x | index de démo (paquets piégés) + flux RSS de démo | `127.0.0.1:8081` |
| httpx, pydantic, rapidfuzz, packaging, feedparser, Jinja2, HTMX | — | client HTTP, schémas, typosquat, versions, RSS, pages | — |

Groupe de sécurité : 22, 8080 et 3128 ouverts aux seules IP de l'équipe ; rien d'autre.

## Les flux de données

```
                          ┌───────────────────────── boîtier (EC2) ─────────────────────────┐
 Poste dev ──(1)──────────▶ index :8080 ──(4)──▶ pypi.org / pypiserver de démo              │
           ◀─(2)──────────           │                                                      │
           ──(3) CONNECT──▶ proxy :3128 ─────────(opaque TLS)──▶ n'importe quel site autorisé│
                          │      │ Flow                │ nouvelle version                   │
                          │      ▼                     ▼                                    │
                          │   egress ──corrélation──▶ pipeline ──(5)──▶ api.osv.dev          │
                          │      │                     │      ──(6)──▶ pypi.org JSON         │
                          │      │──(7)──▶ rdap.org    │      ──(8)──▶ flux RSS              │
                          │      ▼                     ▼                                    │
                          │   egress_agent ──(9)──▶ Ollama :11434 ◀──(9)── llm              │
                          │                     SQLite ◀── tout                              │
 Navigateur ──(10)────────▶ console :8080                                                   │
                          └─────────────────────────────────────────────────────────────────┘
```

| # | De → vers | Protocole | Contenu |
|---|---|---|---|
| 1 | poste → index | HTTP `GET /simple/<paquet>/` puis `GET /files/<fichier>` | nom du paquet ; en-tête `User-Agent` de pip ; IP source = identité du poste |
| 2 | index → poste | HTML PEP 503 (liens + `#sha256=` + `data-requires-python`), puis l'archive `.whl`/`.tar.gz` | versions **visibles seulement** ; octets du paquet vérifiés |
| 3 | poste → proxy | `CONNECT domaine:443 HTTP/1.1`, puis octets TLS opaques | le sas lit : domaine, port, heure, octets montants/descendants, durée. **Jamais le contenu** |
| 4 | index → amont | HTTPS, Simple API JSON PEP 691 + téléchargement des fichiers | nom du paquet ; fichiers publics |
| 5 | pipeline → OSV | HTTPS `POST /v1/query` `{"package":{"name","ecosystem":"PyPI"},"version"}` | nom + version seulement ; réponse : avis CVE/MAL |
| 6 | pipeline → PyPI JSON | HTTPS `GET /pypi/<nom>/<version>/json` | nom + version ; réponse : date, mainteneurs, `yanked`, changelog |
| 7 | egress → RDAP | HTTPS `GET /domain/<domaine>` | un domaine ; réponse : date de création |
| 8 | veille → flux RSS | HTTPS `GET` | rien d'envoyé ; réponse : XML des articles |
| 9 | sas → Ollama (local) | HTTP `POST /api/chat` `{"model","messages","format":<schéma>,"options":{"temperature":0},"stream":false}` | constats, extraits ≤ 200 car., changelog, articles, résumés de flux ; réponse JSON validée |
| 10 | navigateur → console | HTTP, pages HTML + fragments HTMX | états, signaux, alertes, décisions humaines |

**Ce qui ne quitte jamais le boîtier :** le code des projets de la PME, la liste complète de ses
dépendances, l'identité de ses postes, le contenu de ses connexions, les verdicts.

**Ce qui sort :** des noms de paquets avec leurs versions (5, 6), des noms de domaines (7), des
lectures de flux publics (8).

## Les données stockées (SQLite)

| Table | Une ligne = | Champs clés |
|---|---|---|
| `versions` | une version d'un paquet vue par le sas | état, date de publication, date de découverte, raison |
| `files` | un fichier de cette version | nom, SHA-256, chemin en cache |
| `signals` | un indice levé | source (checks, diff, llm, watch, egress), niveau, sorte, preuve JSON |
| `installs` | un fichier servi à un poste | poste, paquet, version, heure |
| `flows` | une connexion sortante | poste, domaine, port, octets, durée |
| `domains` | un domaine vu | première vue, date RDAP, bloqué |
| `hosts` / `ci_allowlist` | un poste et sa liste fermée | type `dev` ou `ci` |
| `alerts` | une alerte de sortie | poste, résumé français, signaux cités |
| `journal` | une décision | acteur, action, sujet, charge JSON, hash précédent, hash |

## Les états d'une version

```
            découverte
                │
                ▼
          ┌─quarantine─┐── délai écoulé, rien ──▶ approved
          │            │── correctif CVE, propre ─▶ fast_track
          │            │── 1 signal fort / LLM / article ─▶ review ──clic──▶ approved | blocked
          └────────────┘── signal bloque / 2 forts / corrélation ─▶ blocked
     approved ── signal tardif (veille, corrélation) ──▶ blocked | review
```

## Configuration d'un poste (une fois)

```bash
pip config set global.index-url http://<ip-du-sas>:8080/simple
setx HTTPS_PROXY http://<ip-du-sas>:3128
```

Côté pare-feu de la PME, on n'autorise la sortie que depuis le sas. Dans la démo, cette règle n'est
pas appliquée sur le PC ; elle est dite.
