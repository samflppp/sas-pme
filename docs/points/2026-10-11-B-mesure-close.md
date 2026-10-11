# Point B (Mouabd19) — mesure finale complète (M3) — 2026-10-11

## Réponse à C (`C-mesure-ligne3`)
- **Merci, c'est reçu.** La ligne 3 est sur `main` (PR #84) : **la mesure finale est complète**.

## Le résultat (`mesure/resultats.md`)
| Ligne | Détection (malveillantes arrêtées) | Fausses alertes (saines arrêtées) |
|---|---|---|
| 1. Contrôles seuls (nom + code) | 93 / 128 (73 %) | 0 / 98 (0 %) |
| 2. + sandbox | 103 / 128 (80 %) | 0 / 98 (0 %) |
| 3. + LLM/RAG | 103 / 128 (80 %) | 0 / 98 (0 %) |

Sur 98 versions saines, 48 sont des paquets peu connus, qui n'ont servi à régler aucune règle :
**0 fausse alerte**.

## La lecture à garder pour le deck et la fiche de défense
- **La sandbox paie :** +10 détections, sans fausse alerte. Elle voit ce que le code cache : un
  DNS vers l'attaquant, une commande, un fichier lu.
- **Le LLM n'ajoute aucune détection, et c'est voulu.** Le code décide, le LLM alerte et explique.
  Sur les 5 versions où il pouvait changer le verdict, il n'en change aucun, et il ne crée aucune
  fausse alerte. Sa valeur se voit sur la fiche d'une version, pas dans ce tableau : une
  explication en français, avec des références réelles (CWE, ATT&CK, cas connus du RAG).
- **La réponse au premortem** (« une règle simple fait-elle aussi bien que l'IA ? ») :
  - pour **détecter**, oui, et nous l'assumons : c'est ce qui rend le verdict fiable et
    vérifiable ;
  - pour **expliquer** à un CTO sans équipe sécurité, il faut le LLM.
- **Phrase pour le jury :** « 80 % des versions malveillantes arrêtées, 0 fausse alerte sur 98
  versions saines. La détection vient de règles et d'une sandbox qu'on peut vérifier ; l'IA
  explique, elle ne décide pas. »
- **Limite à dire d'avance :** la sandbox installe sans les dépendances. Ultralytics, dont la
  charge part à l'import, n'est donc pas vue par elle. C'est le rôle du délai de 3 jours et de la
  veille, qui l'auraient vue retirée.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| A (Sam) | `docs/defense.md` § 3 : le tableau ci-dessus et la lecture ; § 4 : la limite des dépendances (point `B-mesure-finale`) | H22 | ok |

## Ensuite
- La diapositive de mesure, quand Mouabd19 la demande.
