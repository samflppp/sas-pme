# Point B (Mouabd19) — M1 : `pipeline.decision_humaine` — 2026-10-10

## Fait
- **Signature retenue (celle proposée par A) :**
  `pipeline.decision_humaine(base, eco, nom, version, etat, raison, acteur) -> Verdict`.
- `etat` vaut `approuvee` ou `bloquee` (un `Etat` ou le texte). Sinon → `ValueError`. Une
  raison vide → `ValueError`. Une version qui n'est pas `a_revoir` → `ValueError`. Une version
  inconnue → `KeyError`.
- La décision devient un signal `HUMAIN` : `approbation_humaine` (INFO) ou `blocage_humain`
  (BLOQUANT). Sa preuve porte `extrait` (« acteur : raison ») et `acteur`.
- La politique décide ensuite avec tous les signaux de la version, puis on écrit le verdict et
  l'état. L'acteur du journal est l'admin.
- **Politique** : une approbation humaine lève un signal FORT, **jamais un BLOQUANT**. Une
  « approbation » qui vient d'une autre source (LLM, veille, statique, sandbox) ne compte pas.
- Une version approuvée par un humain est **publiée au tour suivant** de `traiter()`.
- 218 tests passent. Le code a été cassé deux fois pour voir les tests au rouge.

## Réponses à vos demandes
- **(A, signature de `decision_humaine`)** Oui, ta proposition telle quelle.

## Ensuite
- Analyse statique du code, rapport de sandbox → signaux, LLM, paquets de démo.
