# Journal de B (Mouabd19) : pipeline et IA

## 2026-10-10 — M0 complet côté B : corpus et boucle de traitement (`claude/wonderful-einstein-wqp2nb`, PR samflppp/sas-pme#3)
- **Fait :**
  - **Corpus** (`demo/corpus/`, tâche « en attendant » de M0) : 30 versions PyPI malveillantes tirées
    d'OpenSSF malicious-packages et 50 mises à jour saines de paquets populaires. Ce ne sont que des
    noms et des versions : aucune archive téléchargée, rien d'exécuté. Repris de la branche
    `claude/loving-volta-hy0y2q` par un merge.
  - **`pipeline.traitement.traiter(base)`** pour le point H3 : il prend les versions `en_attente`
    dont le délai est écoulé, les passe `en_analyse`, les télécharge (sha256 vérifié), lance
    `sandbox.executer` (C), enregistre le rapport, applique la politique, enregistre le verdict,
    puis appelle `signature.publier` (C) et passe la version en `publiee`.
  - **Garde-fous :** une analyse ratée passe la version `a_revoir`, jamais `approuvee`. Si la
    publication échoue, la version reste `approuvee` mais pas `publiee`. Sans le module de C, rien
    n'est traité (`RuntimeError`).
  - 57 tests passent.
- **Pour les autres :**
  - **C :** `traiter()` importe `plateforme.sandbox.executer` et `plateforme.signature.publier`,
    avec les signatures de `docs/contrats.md` § 3 et § 4. Le nom de module passé à la sandbox est
    `nom.replace("-", "_")` ; c'est la roue (`.whl`) qui est exécutée en priorité. `publier()`
    reçoit toutes les archives et le `verdict_id`.
  - **A :** il faudra lancer `traiter(base)` régulièrement (une boucle ou une tâche de fond) ;
    à décider ensemble au point H3.
- **J'attends :** C, les stubs `sandbox.executer` et `signature.publier`. Sans eux, le point H3 est bloqué.

### Avancement M0 par rapport à la roadmap (vu par B, le 2026-10-10)

| Qui | Roadmap M0 | État |
|---|---|---|
| A | `commun/`, `pyproject`, `plateforme/db`, web (connexion, catalogue) | **fait**, sur `main` (PR 1, 2, 5) |
| A | en attendant : maquettes | **fait** (PR 4) |
| B | client PyPI, `demander()`, politique factice | **fait**, PR 3 ouverte |
| B | boucle de traitement (nécessaire au point H3) | **fait**, PR 3 |
| B | en attendant : corpus (30 malveillantes, 50 saines) | **fait**, PR 3 |
| C | AWS (VPC, sous-réseau privé sans Internet), pypiserver | **rien sur `main`** |
| C | stubs `sandbox.executer` et `signature.publier` | **rien sur `main`** : bloque le point H3 |

**Point H3 :** pas encore atteignable. Il manque la partie de C, et l'appel à `traiter()` côté web
ou par une tâche de fond.

## 2026-10-10 — M0 : client PyPI, `demander()`, politique factice (`claude/wonderful-einstein-wqp2nb`, PR samflppp/sas-pme#3)
- **Fait :**
  - `plateforme/pipeline/pypi.py` : versions stables non retirées, `derniere_version_mure()` (délai
    3 jours), `telecharger()` avec vérification du sha256 ; nom de paquet validé avant tout appel
    réseau ; amont réglable par `SAS_PYPI_URL`.
  - `pipeline.demander(eco, nom)` : enregistre la dernière version mûre `en_attente` dans
    `Base(SAS_DB)` ; nom normalisé (`Requests` devient `requests`).
  - `pipeline.politique.decider(signaux)` : **factice**, approuve tout, même un signal `BLOQUANT`.
  - 42 tests passent, dont un test d'intégration avec la vraie page web de A.
- **Pour les autres :**
  - **A :** ton web utilise maintenant le vrai `demander()`. Il lève `LookupError` (paquet inconnu
    ou trop récent), `ValueError` (nom invalide) et `NotImplementedError` (npm). Ta page
    `/demander` les renvoie aujourd'hui en erreur 500 : à transformer en message (ton dossier, je
    n'y ai pas touché).
  - **C :** le client lit `/pypi/<nom>/json`. Il faut vérifier que la source amont de démo
    (pypiserver) répond à cette adresse.
- **J'attends :**
  - **C :** les stubs `sandbox.executer` et `signature.publier`, pour brancher la boucle de traitement.
  - **A :** la relecture de la PR #3.
- **En cours / suite :**
  - `b/traitement` : `versions_a_traiter`, puis téléchargement, sandbox, politique, verdict et publication.
  - Le corpus `demo/corpus/` existe déjà sur la branche `claude/loving-volta-hy0y2q` (session
    précédente), sans PR : à relire puis à proposer en PR. Ne pas le refaire.
