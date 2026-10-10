# sas-pme — consignes pour l'agent (lues à chaque prompt)

Plateforme agréée connectée à Internet + passerelle sans Internet : les serveurs sensibles d'une PME
n'installent par pip et npm que des versions attendues 3 jours, analysées localement (statique,
sandbox, LLM + RAG), signées. Projet de hackathon : **le but est un MVP démontrable, pas plus.**

## Qui je sers

Demander au début de la session, si ce n'est pas dit : **A (Sam), B (Mouabd19) ou C (STEUSSO)** ?
Puis rester dans les dossiers de cette personne (`docs/organisation.md` § 3).

- **A :** `plateforme/web/`, `plateforme/db/`, `demo/script.md`
- **B :** `plateforme/pipeline/`, `mesure/`, `demo/paquets/`, `demo/corpus/`
- **C :** `plateforme/sandbox/`, `plateforme/signature/`, `passerelle/`, `infra/`, `demo/reseau.md`

## Règles

1. Lire les docs importées ci-dessous avant de coder. Coder contre `docs/contrats.md` et `commun/`.
2. Ne jamais modifier `commun/` ni le dossier d'une autre personne sans le dire à l'utilisateur.
3. Tests : test qui échoue, code minimal, test vert, puis casser une fois le code regardé pour voir le
   test tomber au rouge.
4. Une branche courte par tâche (`a/…`, `b/…`, `c/…`), PR vers `main` au bout de 1 à 3 h.
5. Le code décide, le LLM alerte et explique : aucun chemin de code ne laisse le LLM ou un article
   approuver une version ou abaisser un risque.
6. Aucun secret dans Git (clé de signature, clés AWS). Ne jamais exécuter un échantillon malveillant
   hors de la sandbox.
7. Rester dans le périmètre du jalon en cours (`docs/roadmap.md`). Une idée hors périmètre se note,
   elle ne se code pas.

## Contexte importé

@docs/contexte.md
@docs/architecture.md
@docs/contrats.md
@docs/roadmap.md
@docs/organisation.md
@docs/sauvegardes.md
