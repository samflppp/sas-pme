# sas-pme

**Vos serveurs n'installent que ce qu'on a vérifié.**

Les serveurs sensibles d'une PME n'ont pas accès à Internet. Ils prennent leurs paquets pip et npm dans
une **passerelle sans Internet**. Cette passerelle ne reçoit que des versions **attendues 3 jours,
analysées localement** (code, sandbox, LLM + RAG) et **signées** par une plateforme agréée, qui est la
seule machine connectée.

Projet de hackathon, Track 3 « Open Track » (IA × cybersécurité défensive). Objectif : un MVP
démontrable.

## À lire

| Document | Contenu |
|---|---|
| [docs/contexte.md](docs/contexte.md) | problème, client idéal, produit, principes, décisions, équipe |
| [docs/architecture.md](docs/architecture.md) | zones, composants, flux, sandbox, RAG, démo sur AWS, dépôt |
| [docs/contrats.md](docs/contrats.md) | interfaces entre A, B et C : types, fonctions, API de la passerelle, manifeste signé |
| [docs/roadmap.md](docs/roadmap.md) | jalons M0 à M3, points de rencontre, ordre de coupe, démo |
| [docs/organisation.md](docs/organisation.md) | branches, propriété des dossiers, routine, consignes aux agents |
| [docs/sauvegardes.md](docs/sauvegardes.md) | ce qu'on sauvegarde, où, et le cloud |
| [docs/roadmap.pdf](docs/roadmap.pdf) | la roadmap à imprimer |

`CLAUDE.md` (Claude Code) et `.kiro/steering/sas-pme.md` (Kiro) font lire ces documents à l'agent à
chaque prompt.

## Démarrer

```bash
git clone https://github.com/samflppp/sas-pme.git
cd sas-pme
git switch -c <a|b|c>/<tâche>
```

Le code arrive en M0 (`commun/`, `pyproject.toml`). Ensuite :
`python -m venv .venv && .venv\Scripts\activate && pip install -e ".[dev]"`. Python 3.12 au minimum.
