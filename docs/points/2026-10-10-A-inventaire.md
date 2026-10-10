# Point A (Sam) — proposition : le sens de l'inventaire de la passerelle — 2026-10-10

## Fait
- **`docs/contrats.md` § 4** : ce que veut dire `/v1/inventory`. Le format existait déjà
  (`EntreeInventaire` : `ecosysteme`, `nom`, `version`, `telechargements`, `dernier`) et **ne
  change pas** : `commun/modeles.py` n'est pas touché.
- Précisé :
  - ce qui compte comme un téléchargement : `GET /packages/<fichier>` avec la réponse 200, pas les
    pages `/simple/` ;
  - le nom normalisé selon la PEP 503, et la version lue dans le nom du fichier ;
  - le total cumulé depuis l'installation ;
  - les entrées attendues : toute version du dépôt, même jamais téléchargée, et toute version
    révoquée déjà téléchargée ;
  - l'ordre de la liste, et une ligne de journal illisible ignorée.
- Pourquoi maintenant : c'est le dernier point de C pour clore le M1, et la page « Inventaire » de A
  (M2) le lira. Fixer le sens avant le code évite un aller-retour.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C | Valider ou corriger ces précisions (commentaire sur la PR), puis coder `/v1/inventory` dessus. Si un point est coûteux à lire dans les journaux de pypiserver (par exemple les versions révoquées), le dire. | clôture du M1 | ok / corrections |
| B | Relire (contrat commun). Rien ne change pour le pipeline. | — | ok |

## Ensuite
- Une fois le M1 clos : la page « Inventaire » (M2).
