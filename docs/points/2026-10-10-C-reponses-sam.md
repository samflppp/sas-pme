# Point C (STEUSSO) — réponses à Sam (journal, révocation, PR #54) et à B (C4, C6) — 2026-10-10

## Fait
- **`SAS_CLE_JOURNAL` (A1)** : `installer.sh` tire la clé HMAC du journal **sur la plateforme**
  (`~/.sas-cle-journal`, 64 caractères hexadécimaux, 0600, jamais dans Git) : c'est le fichier que
  lit `demo/script.md`. La fin d'`installer.sh` affiche la ligne `export SAS_CLE_JOURNAL=…`.
- **Révocation selon la règle de l'inventaire (B, C4)** : `/v1/revoke` compare le nom PEP 503 et la
  version PEP 440 de chaque archive (`passerelle.inventaire.meme_version`). La règle « `-` devient
  `_` » ratait `zope.interface-6.0.tar.gz`. Constaté sur AWS : wheel `zope_interface-6.0-…` et
  sdist `zope.interface-6.0.tar.gz` publiés signés, puis révoqués → 0 fichier restant.
- **Nonces et registre réservés au récepteur (B, C6)** : déplacés dans `/var/lib/sas-recepteur`
  (`recepteur`, 0700). `installer.sh` y déplace les fichiers d'une passerelle déjà installée.
  Constaté sur AWS : `sudo -u pypi touch /var/lib/sas-recepteur/x` → `Permission denied`.
- 3 tests neufs, chacun vu au rouge par mutation (sdist ratés, nom ou version non normalisés).

## Réponses à vos demandes
- **(A-correctifs-a1-a2 : relire, poser `SAS_CLE_JOURNAL` dans `infra/`)** Relu, ok. Aucun script
  de `infra/` ne lance le web : c'est `demo/script.md`. La clé est donc tirée par `installer.sh` à
  l'endroit que lit ce script.
- **(PR #54, A3 et A4)** Relue : ok, 461 tests verts chez moi, aucun dossier de C touché. Détail en
  commentaire de la PR.
- **(PR #50 : ancrer la tête du journal à la passerelle)** **Ok, après H16.** Champs `journal_seq`
  et `journal_hash` dans `Manifeste` (PR `commun/` à trois). La passerelle garde la dernière paire
  dans `/var/lib/sas-recepteur` (comme les nonces) et refuse un `journal_seq` qui recule ; elle
  l'expose par `GET /v1/journal-ancre`, en TLS mutuel.
- **(PR #45 et B C4 : 200 ou 404 quand rien n'est retiré)** **200, avec `retire: []`.** Une version
  absente de la passerelle est dans l'état voulu. Un 404 ferait lever `revoquer()`, et la
  plateforme laisserait la version `publiee` : l'admin ne pourrait plus la marquer révoquée (le
  souci de Sam). Le risque que voyait B, une révocation qui rate des fichiers, est réglé à la
  source par C4. La liste `retire` reste dans la réponse pour le journal.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| B | Tes autres constats C1, C2, C3, C5, C7 : je les traite ensuite, dans cet ordre (C1 à C3 sont prioritaires pour H16). | H16 | — |

## Ensuite
- B : C1 (sandbox rendue aveugle par 110 000 lignes), C2 (traces effaçables), C3 (scp sans
  signature), C5 (DNS du VPC), C7 (mineurs). Puis les sauvegardes.
