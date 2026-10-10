# Point A (Sam) — page « Inventaire » (M2) — 2026-10-10

## Fait
- **`GET /inventaire`**, pour tout compte connecté, avec un lien « Inventaire » dans la navigation.
  - La page lit la passerelle à chaque affichage (`signature.lire_inventaire`, C, injectable dans
    `creer_app`).
  - Elle garde l'instantané en base (`enregistrer_inventaire`), pour `base.inventaire()`.
  - Si la passerelle ne répond pas, la page le dit (502), et l'instantané précédent reste.
- **`croiser(entrees, versions)`** rapproche chaque entrée de l'inventaire de la version de la
  plateforme. Les noms sont comparés en PEP 503 et les versions en PEP 440, des deux côtés (remarque
  de B) : `Demo_X 1.10.0` sur le dépôt est bien `demo-x 1.10` sur la plateforme. Une version
  illisible est comparée telle quelle.
- **Les alertes**, en tête de la liste et en rouge :
  - **révoquée ou bloquée depuis, et téléchargée N fois** : un serveur l'a peut-être encore. C'est
    l'alerte que le contrat § 4 désigne comme celle qui compte ;
  - révoquée ou bloquée depuis, mais encore sur le dépôt (la révocation n'a pas tout retiré) ;
  - **inconnue de la plateforme** : présente sur le dépôt sans y avoir été approuvée ;
  - sur le dépôt alors que la version n'est pas « publiee » sur la plateforme (approuvée, à revoir…).
- Le nombre d'alertes est affiché en haut (`data-alertes`). Une version publiée n'est pas une
  alerte. Un nom venu de la passerelle est échappé.
- 16 tests (`tests/plateforme/test_inventaire_web.py`), rouges avant le code (le module n'existait
  pas). Six mutations ont été vues rouges : noms non normalisés, versions non normalisées, version
  publiée en alerte, pas de tri, instantané non gardé, version inconnue sans alerte. Suite
  complète : 477 verts, 7 sautés.

## Pas fait
- La page n'a pas été vue dans un navigateur : seul le HTML rendu est testé.
- Le tableau de bord ne compte pas encore les alertes de l'inventaire. Je pourrai l'ajouter après
  H16 si vous le voulez.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| — | Aucune. À voir pendant la répétition H16 : après la révocation de la 1.2, `/inventaire` doit la montrer en alerte. | — | — |
