# Journal de A (Sam) : plateforme web

## 2026-10-10 — Suivi unifié et fusion du M0 de C (PR samflppp/sas-pme#6)
- **Fait :**
  - Un seul système de suivi : `docs/journal/`. Le point de C est passé dans `c.md`, et
    `docs/points/` est retiré.
  - Le format du journal reprend le tableau des demandes de C (avec la colonne « Bloquant pour »)
    et sa section « Réponses à vos demandes ».
  - `CLAUDE.md` n'a plus qu'une règle 8 ; `docs/organisation.md` § 9 est aligné.
  - Fusion de la PR #6 de C : infra AWS, stubs sandbox et signature. 75 tests passent.
- **Disponible pour vous :** `docs/journal/README.md`, le modèle d'entrée à suivre.
- **Demandes :**

  | À | Demande | Bloquant pour | Réponse attendue |
  |---|---|---|---|
  | B | Répondre à C sur les dépendances : `publier()` reçoit-il les archives des dépendances de `requests`, ou fait-on la démo M0 avec `pip install --no-deps` ? | H3 | dépendances ou `--no-deps` |

## 2026-10-10 — web : erreurs du pipeline affichées, base passée à `demander()` (`a/web-erreurs`)
- **Fait :**
  - La page `/demander` affiche les erreurs prévues de `pipeline.demander` sur le formulaire, sans
    erreur 500 :
    - `LookupError` → 404, avec le message de B (paquet inconnu, ou aucune version assez ancienne) ;
    - `ValueError` → 400 ;
    - `NotImplementedError` → 400, « npm n'est pas encore pris en charge ».
  - Le web passe **sa** base au vrai pipeline (`demander(eco, nom, base=base)`) : plus de seconde
    connexion ouverte sur `SAS_DB`.
  - 61 tests passent ; les deux nouveaux ont été cassés une fois.
- **Pour les autres :**
  - **B :** rien à changer. Garde ces trois exceptions comme contrat de `demander()`.
- **Réponses aux demandes de C** (point du 2026-10-10, PR #6) :
  - *Qui appelle `publier()` ?* Le pipeline de B : `pipeline.traitement.traiter(base)` (PR #3
    fusionnée). Les variables `SAS_PASSERELLE_SSH` et `SAS_PASSERELLE_CLE` vont donc dans
    l'environnement du processus qui lance `traiter()`, sur la plateforme.
  - *Port du web :* 443 depuis les IP de l'équipe me va. Sam envoie son IP publique.
- **En cours / suite :**
  - Brancher `traiter(base)` en tâche de fond de l'application web, toutes les 60 s (demande de B),
    pour le point H3.
  - M1 : comptes et rôles, file d'attente, décision humaine (maquettes dans
    `plateforme/web/maquettes/`).

## 2026-10-10 — M0 de A (PR #1, #2, #4, #5)
- **Fait :**
  - `commun/modeles.py`, avec les contrats ;
  - `pyproject.toml` ;
  - `plateforme/db`, la base SQLite et le journal chaîné ;
  - le web : connexion, catalogue, demande, fiche ;
  - les maquettes M1.
- **Pour les autres :** `Base` est dans `plateforme/db/acces.py` (voir `docs/contrats.md` § 2).
