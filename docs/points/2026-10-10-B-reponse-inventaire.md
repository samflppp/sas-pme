# Point B (Mouabd19) — relecture du contrat § 4, l'inventaire (PR #38) — 2026-10-10

## Réponse à A (relire `docs/contrats.md` § 4)
**Ok, aucun désaccord.** Rien ne change pour le pipeline, qui n'appelle ni `lire_inventaire()`
ni `enregistrer_inventaire()`.

- **Les noms se recoupent.** `pipeline.demander()` enregistre déjà chaque paquet, et chacune de
  ses dépendances, sous son nom PEP 503 (`canonicalize_name`). C'est la règle du contrat.
- **Garder les versions révoquées déjà téléchargées me va.** C'est aussi ce qu'il faut à la
  veille RSS. Quand un article vise une version **publiée**, le journal note
  `article_version_publiee` sans la révoquer. L'inventaire dit alors quels serveurs l'ont.

Trois remarques, aucune ne bloque :

1. **Comparer les versions sous leur forme normalisée (A, page inventaire).**
   - La passerelle rend la version PEP 440 lue dans le nom du fichier (`str(Version(…))`).
   - La base garde la version telle que PyPI l'affiche.
   - Elles diffèrent rarement, pour quelques vieux paquets (`1.0-beta1` contre `1.0b1`). Pour
     croiser les deux sans rien rater, je te propose de comparer avec
     `packaging.utils.canonicalize_version` des deux côtés.
2. **Une révocation qui ne retire rien devrait répondre 404, pas 200 (C, contrat § 4,
   `/v1/revoke`).**
   - La passerelle ne cherche les archives qu'en remplaçant `-` par `_`, sans la règle PEP 503
     complète.
   - Ça rate par exemple une archive source au nom pointé, comme `zope.interface-6.0.tar.gz`. La
     route rend alors `200 {"retire": []}`, et la plateforme croit la version retirée alors
     qu'elle est encore servie.
   - Les roues (`.whl`) ne sont pas touchées : c'est le cas courant de la démo.
   - Je propose deux changements :
     - chercher l'archive avec la même règle que l'inventaire (`parse_wheel_filename` /
       `parse_sdist_filename`) ;
     - ajouter `404 rien à retirer` aux réponses du tableau.
3. **`machines` hors contrat (question de C) : ok.** Le pipeline ne le lit pas, il peut rester
   dans le JSON brut pour le MVP.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C | Remarque 2 : `/v1/revoke` avec la règle de l'inventaire, et 404 quand rien n'est retiré | — | ok / non |
| A | Remarque 1 : `canonicalize_version` pour croiser l'inventaire et la base | — | ok / non |
