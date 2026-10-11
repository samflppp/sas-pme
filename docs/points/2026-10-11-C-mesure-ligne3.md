# Point C — ligne 3 de la mesure (+ LLM/RAG), lancée sur AWS — 2026-10-11

## Réponses à B (`B-mesure-finale`)
**Fait.** `main` (PR #82) est redéployé sur la plateforme ; ton bloc a été lancé tel quel, en 323 s.
Les échantillons ont seulement été lus : la ligne 2 reprend les rapports de sandbox du cache, et
la ligne 3 n'envoie au LLM que des constats. `mesure/resultats.md` régénéré est commité ici.

| Ligne | Détection (malveillantes arrêtées) | Fausses alertes (saines arrêtées) |
|---|---|---|
| 1. Contrôles seuls (nom + code) | 93 / 128 (73 %) | 0 / 98 (0 %) |
| 2. + sandbox | 103 / 128 (80 %) | 0 / 98 (0 %) |
| 3. + LLM/RAG | **103 / 128 (80 %)** | **0 / 98 (0 %)** |

- **LLM interrogé sur 5 versions** (celles qui n'étaient pas encore arrêtées et avaient un constat
  MOYEN hors du LLM) : il n'en arrête **aucune de plus**, et il ne crée aucune fausse alerte.
- Les 25 malveillantes manquées sont les mêmes qu'à la ligne 2 (dont ultralytics 8.3.41, 8.3.42
  et 8.3.46).
- Lecture, conforme à ton point : le code décide, le LLM explique. Il ne dégrade rien (0 fausse
  alerte), et la détection vient des contrôles et de la sandbox.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| A (Sam) | Reporter la ligne 3 dans `docs/defense.md` § 3 (demande de B) | H22 | ok |
