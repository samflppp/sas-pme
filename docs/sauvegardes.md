# Sauvegardes : mon avis

## Oui, le local les rend plus faciles

Tout ce qui compte vit sur deux machines connues, dans quelques dossiers connus. Il n'y a rien de
dispersé chez des fournisseurs. Et presque tout est **reconstructible**, car les paquets sont publics.
Ce qui ne se reconstruit pas, c'est **notre jugement** : les verdicts, le journal et les clés.

| Donnée | Où | Gravité de la perte | Reconstructible ? |
|---|---|---|---|
| **Clé privée de signature** | plateforme | **critique** : sans elle, plus rien ne se publie ; volée, quelqu'un publie à notre place | non |
| Base (versions, verdicts, signaux, journal chaîné, comptes) | plateforme | **forte** : toutes les décisions et leurs preuves, utiles pour un audit | non |
| Archives approuvées | plateforme et passerelle | moyenne | oui, re-téléchargement et vérification du hash |
| Dépôts de la passerelle | passerelle | faible | oui, la plateforme republie tout |
| Index RAG, modèles Ollama | plateforme | faible | oui, quelques heures |
| Configuration (listes fermées, réglages, certificats du lien) | les deux | moyenne | à la main |

## Le schéma proposé (règle 3-2-1)

1. **Copie locale quotidienne, sur site.** `restic` vers un disque ou un NAS de la PME : base,
   configuration, archives approuvées. Copie chiffrée, rétention de 30 jours.
2. **Copie hors ligne hebdomadaire.** Un disque USB chiffré qu'on débranche. Il protège d'un
   rançongiciel qui chiffrerait aussi le NAS.
3. **Copie dans le cloud : oui, mais en option, et seulement chiffrée côté client.** `restic` vers S3
   (ou un hébergeur français), avec une clé que **seule la PME détient**. Le fournisseur ne voit que
   du chiffré. Ce qu'on y met n'est pas sensible : des paquets publics, des verdicts et un journal.
   C'est la seule copie qui survit à un incendie ou à un vol du local.

**La clé privée de signature ne va jamais dans le cloud.** Elle a deux copies hors ligne (USB chiffré
au coffre, et papier). La clé publique, elle, est déjà sur chaque passerelle.

**Les serveurs sensibles de la PME** ne font pas partie de notre périmètre de sauvegarde : ce sont
leurs données. On peut le proposer plus tard, c'est la même mécanique.

## Ce qui est dans le MVP

- **M2 (C) :** un script `infra/sauvegarde.sh` (`restic` local) et un **test de restauration** :
  1. effacer la base ;
  2. la restaurer ;
  3. vérifier que la chaîne du journal est intacte.
- **Dans le deck :** une ligne, « Sauvegarde locale chiffrée, copie hors ligne, cloud en option et
  chiffré par vous ».
- **Le cloud chiffré :** en feuille de route. Le code est le même avec une autre destination
  `restic`.
