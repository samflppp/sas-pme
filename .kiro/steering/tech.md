# Technique

## Pile

- Python 3.12, FastAPI, `httpx`, `uvicorn`.
- SQLite (un seul fichier) pour l'état et le journal append-only.
- Ollama, modèle `qwen2.5-coder:7b`, sortie JSON contrainte (`format` JSON schema).
- `rapidfuzz` pour le typosquat ; `packaging` pour les versions ; `feedparser` pour les flux RSS.
- Proxy CONNECT maison en `asyncio` (aucun déchiffrement TLS).
- Console : FastAPI + Jinja2 + HTMX, sans build front.
- Tests : `pytest`.

## Déploiement de la démo

- Une instance EC2 `g4dn.xlarge` (GPU T4) joue le boîtier posé dans le placard de la PME : sas, proxy,
  Ollama, console.
- Le PC du développeur joue un poste de la PME : `PIP_INDEX_URL` et `HTTPS_PROXY` pointent vers l'EC2.
- Un `pypiserver` local à l'EC2 sert le corpus de démo (paquets piégés construits d'après des cas
  réels) ; aucune démo ne dépend du vrai PyPI pour un cas malveillant.
- Aucun service AWS managé (ni Bedrock, ni Lambda, ni DynamoDB) : le pitch est « tout local ».

## Règles

- Le chemin de `pip` n'attend jamais le LLM ni la veille.
- Toute sortie de LLM est validée par un schéma ; hors schéma, elle est ignorée et journalisée.
- Le journal n'est jamais réécrit ni effacé.
- Aucun secret dans le dépôt.
