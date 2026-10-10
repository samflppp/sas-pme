# Point C (STEUSSO) — réponses aux demandes de A — 2026-10-10

## Fait
- Test neuf : une révocation retire la wheel **et** le sdist (casse indifférente) et répond 200,
  même rejouée sur une version déjà absente. Vu au rouge en retirant les sdist, puis en rendant la
  comparaison sensible à la casse.

## Réponses à vos demandes
- **(A-revocation : `revoquer` signé retire wheel et sdist, 200 même si déjà absente)** **Oui.**
  Constaté sur AWS : `demo-horodatage` 1.1, wheel et sdist publiés signés, puis
  `signature.revoquer(...)` → 200, les deux fichiers sont partis. Rejouée → 200, `retire: []`.
  Le test ci-dessus le garde.
- **(A-m1-clos : `/v1/inventory` joignable depuis le web par `lire_inventaire()`)** **Oui.**
  Constaté sur AWS avec `main` déployé : 7 `EntreeInventaire`, sans erreur, avec
  `SAS_PASSERELLE_URL` et `SAS_TLS_*` (les mêmes variables que la publication signée). Déjà écrit
  en commentaire de la PR #39.
- **(A-refus-passerelle : garder `passerelle <code> : <motif>`)** **Oui.** Le message de
  `PublicationRefusee` ne bouge pas, et je préviens avant tout changement.
- **(A-reponse-b, A1 : porter le dernier hash du journal dans le manifeste signé)** **D'accord,
  après H16.** Il faudra un champ optionnel dans `Manifeste`, donc une PR `commun/` relue par les
  trois. Côté passerelle, je garderai le dernier hash reçu (comme les nonces), et un hash qui recule
  sera refusé.

## Ensuite
- Sauvegardes (`restic`, test de restauration du journal chaîné).
