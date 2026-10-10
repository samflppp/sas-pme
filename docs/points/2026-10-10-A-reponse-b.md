# Point A (Sam) — réponse à la relecture de B — 2026-10-10

Merci pour la relecture (`2026-10-10-B-relecture.md`, `B-reponse-inventaire.md`). J'ai revérifié
dans le code chacun des constats A1 à A4 : tous sont exacts. Réponses ci-dessous ; les correctifs
partent en PR avant le point H16, dans l'ordre du tableau.

## Réponses à B
| # | Réponse | Correctif prévu |
|---|---|---|
| A1 | **Ok.** `_hash` est un sha256 sans clé : qui a la base peut recalculer toute la chaîne. | Chaque entrée signée en **HMAC-SHA256** avec une clé hors de la base (`SAS_CLE_JOURNAL`, jamais dans Git ; refus de démarrer sans elle hors des tests). Limite qui reste : effacer les **dernières** entrées passe toujours sans clé. Je la dis dans `contrats.md` § 2, et je propose à C d'ancrer plus tard le dernier hash dans le manifeste signé. La phrase au jury devient : « une entrée réécrite ou insérée se voit ; la fin du journal se compare à la passerelle ». |
| A2 | **Ok.** Pas de `ROLLBACK` dans `enregistrer_inventaire` (`acces.py:211`). | Transaction avec `ROLLBACK` sur erreur, et un test avec deux entrées en double qui vérifie qu'une écriture suivante passe. Avant la page inventaire. |
| A3 | **Ok.** Le verrou est propre à l'instance, alors que le dernier hash est lu hors transaction. | Lecture du dernier hash et `INSERT` dans un même `BEGIN IMMEDIATE`. Test avec deux `Base` sur le même fichier et des écritures concurrentes. |
| A4 | **Ok.** `changer_etat` ne vérifie pas l'état de départ, et le journal est écrit dans une autre transaction. | `changer_etat(..., attendu=None)` : `AND etat=?` quand l'état attendu est donné (sinon `ValueError`), et UPDATE + journal dans la même transaction. La décision humaine et la révocation passeront l'état attendu (`a_revoir`, `publiee`). Pour `decision_humaine`, je te demande d'appeler la nouvelle signature (voir « Demandes »). |
| A5 | **Ok, les trois.** | En-tête `Origin` (ou `Referer`) vérifié sur tous les POST ; changer son mot de passe coupe les autres sessions (numéro de version du mot de passe dans la session) ; `SAS_ADMIN_MOTDEPASSE` refusé sous `MDP_MIN`. |
| Inventaire, remarque 1 | **Ok.** | La page inventaire compare les versions avec `packaging.utils.canonicalize_version` des deux côtés (et les noms avec `canonicalize_name`). |

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| B | Quand le correctif A4 sera sur `main`, passer `attendu=Etat.A_REVOIR` à `changer_etat` dans `decision_humaine`, pour qu'une double décision soit refusée au lieu d'écraser la première. | A4 complet | ok |
| C | Pour A1 : d'accord pour, plus tard, porter le dernier hash du journal dans le manifeste signé et le garder côté passerelle ? Pas avant H16. | — | ok / non |
