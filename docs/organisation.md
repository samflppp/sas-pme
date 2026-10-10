# Organisation : travailler à trois, chacun avec son IDE et son agent

## 1. Le principe

Chacun travaille dans **son** IDE avec **son** agent (Claude Code ou Kiro) sur **ses** dossiers. La base
commune, `commun/` et les docs, existe dès H1. On fusionne dans `main` **plusieurs fois par jalon**, pas
seulement à la fin.

## 2. Trois branches longues ou des branches courtes ? Mon analyse

**Trois branches longues, une par personne, fusionnées aux points de rencontre.** Elles semblent
simples, mais elles divergent en quelques heures. Chaque fusion devient une séance d'intégration où
l'on découvre en même temps tous les écarts aux contrats. Et chaque personne travaille contre une
version périmée du code des autres : c'est exactement « travailler dans le vide ».

**Retenu : `main` comme tronc, plus des branches courtes, une par tâche.**
- Une branche par tâche, nommée `a/<tâche>`, `b/<tâche>` ou `c/<tâche>` (ex. `c/recepteur-passerelle`).
- Elle vit **1 à 3 h**, puis une Pull Request vers `main` est fusionnée dès que les tests passent.
- Chacun fait `git pull` de `main` au début de chaque tâche, et voit donc le travail des autres
  quelques heures après au plus.
- Les points de rencontre deviennent de simples vérifications de bout en bout, plus des fusions de
  crise.

**Pourquoi ça ne crée pas de conflits :** chacun possède ses dossiers (§ 3). Deux personnes ne
modifient presque jamais le même fichier. Les seuls fichiers communs ont une règle (§ 4).

## 3. Qui possède quoi

| Dossier | Propriétaire | Les autres |
|---|---|---|
| `commun/` | A écrit en M0 ; ensuite les trois | changement **seulement par PR relue par les trois** |
| `plateforme/web/`, `plateforme/db/` | A | lecture ; B appelle `plateforme/db/acces.py` |
| `plateforme/pipeline/`, `mesure/` | B | lecture ; A appelle `pipeline.demander` et `pipeline.decision_humaine` |
| `plateforme/sandbox/`, `plateforme/signature/`, `passerelle/`, `infra/` | C | lecture ; B appelle `sandbox.executer` et `signature.publier` |
| `demo/` | A : `script.md` ; B : `paquets/`, `corpus/` ; C : `reseau.md` | — |
| `docs/` | les trois | une mise à jour = une PR courte |
| `pyproject.toml` | les trois | une dépendance ajoutée = une ligne, dans sa section commentée |

Toucher le dossier d'un autre, c'est le prévenir d'abord. Un message suffit.

## 4. Les fichiers communs

- `commun/modeles.py` : le contrat. Le modifier, c'est une PR à 3. Ajouter un champ optionnel est
  facile ; retirer ou renommer se négocie.
- `pyproject.toml` : chaque personne a sa section commentée de dépendances.
- `tests/conftest.py` : un bloc par personne.

## 5. Le faux de l'autre (stub)

Chaque interface du fichier `contrats.md` existe **dès M0** sous forme de faux, qui renvoie une valeur
plausible. Ainsi :
- B code le pipeline avant que la sandbox de C existe ;
- A affiche une fiche avant que le verdict de B soit réel.

Quand le vrai arrive dans `main`, le faux disparaît et on ne change rien chez soi.

## 6. La routine de chacun

1. `git switch main && git pull`
2. `git switch -c c/<tâche>` (avec sa lettre)
3. coder avec son agent ; `pytest`
4. `git push -u origin c/<tâche>`, puis ouvrir une PR (`gh pr create --fill`)
5. si les tests passent et que le dossier est le sien : fusion. Si `commun/` est touché : relecture par
   les deux autres.
6. retour à l'étape 1

## 7. Consignes pour les agents (Claude Code, Kiro)

- **Lire `docs/` avant de coder.** `CLAUDE.md` et `.kiro/steering/` le rappellent à chaque prompt.
- **Rester dans les dossiers de sa personne.** Pour toucher ailleurs, demander d'abord.
- Ne jamais modifier `commun/` sans le dire.
- **Méthode de test :** test qui échoue, code minimal, test vert, puis **casser une fois** le code
  regardé pour vérifier que le test tombe au rouge.
- Petits commits ; des messages en français au format `feat:`, `fix:`, `docs:`, `test:`.
- Aucun secret dans le dépôt : ni clé privée de signature, ni clé AWS. Les clés vivent dans `infra/`
  hors Git (`.gitignore`) ou dans les variables d'environnement.
- **Ne jamais installer ni exécuter un échantillon malveillant hors de la sandbox.** Le corpus se
  télécharge et se lit seulement, dans un dossier à part, avec Python lancé en `-I`.

## 8. Les points de rencontre

H3, H10, H16, H22 : 15 min, les trois ensemble, devant la démo de bout en bout. On y vérifie ce qui
marche, on décide des coupes et on ajuste les contrats si besoin. Hors de ces points, on se parle
quand on veut.
