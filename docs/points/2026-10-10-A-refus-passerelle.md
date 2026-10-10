# Point A (Sam) — fiche : un refus de la passerelle n'est pas une panne — 2026-10-10

## Fait
- Sur la fiche d'une version **approuvée mais pas publiée**, deux cas sont maintenant distincts :
  - **refus de la passerelle** (encadré rouge) : « Refusée par la passerelle (401 : signature
    invalide) », avec ce que ça veut dire. Un refus qui se répète signale une clé ou un
    certificat changé, ou une publication qui ne vient pas de la plateforme ;
  - **passerelle injoignable** : « publication retentée au tour suivant », avec le message
    d'erreur.
- Rien ne change chez B ni chez C. Le web lit la raison que `traiter()` écrit déjà
  (« publication échouée : … ») et le message de `PublicationRefusee`
  (« passerelle <code> : <motif> »). `etat_publication(etat, raison)` dans `plateforme/web/app.py`.
- Le motif renvoyé par la passerelle est échappé comme tout le reste.
- 9 nouveaux tests, vus au rouge avant le code, et chaque garde cassée une fois. 350 tests
  passent.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| B | Garder le préfixe `publication échouée : ` dans `_publier` (`pipeline/traitement.py:90`) ; le prévenir avant de le changer. | — | ok |
| C | Garder le message `passerelle <code> : <motif>` de `PublicationRefusee` (`signature/__init__.py:59`) ; le prévenir avant de le changer. | — | ok |

## Ensuite
- La clôture du M1 attend les points de C (inventaire, `ufw`).
