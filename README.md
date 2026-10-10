# sas-pme

**Le sas de sécurité qui fait attendre les mises à jour, pas vos développeurs.**

Un sas local, posé dans la PME, qui :
- retient chaque nouvelle version de paquet Python le temps qu'une IA locale l'examine et lise ce
  qu'Internet en dit ;
- surveille les connexions sortantes des postes ;
- démasque un paquet piégé dès qu'il appelle son serveur, s'il a quand même été installé.

Projet de hackathon, Track 3 « Open Track » (IA × cybersécurité défensive).

**Avant toute chose, lire [`docs/contexte-projet.md`](docs/contexte-projet.md).** Il contient le
problème, le client, les décisions et leurs raisons, l'équipe, le planning et les règles de travail.

## Démarrer

```bash
git clone https://github.com/samflppp/sas-pme.git
cd sas-pme
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS : source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Python 3.12 au minimum.

## Branches

| Branche | Qui |
|---|---|
| `main` | fusions aux points de synchronisation (H6, H13, H17) |
| `pipeline-plateforme` | Sam (A) et Mouabd19 (B) |
| `infra-reseau` | STEUSSO (C) |

Routine : `git pull --rebase`, puis un petit commit, `pytest`, et `git pull --rebase && git push`.

## Documents

- [Contexte complet](docs/contexte-projet.md)
- [Architecture : machines, logiciels, flux de données](docs/architecture.md)
- [Roadmap (PDF)](docs/roadmap.pdf)
- Spec Kiro : [exigences](.kiro/specs/sas-pme/requirements.md) · [design](.kiro/specs/sas-pme/design.md) · [tâches](.kiro/specs/sas-pme/tasks.md)
