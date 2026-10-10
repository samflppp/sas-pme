# Points d'avancement

Un point = un court fichier markdown qui dit **ce que j'ai fait, ce que les autres peuvent utiliser, et
ce que je leur demande**. C'est ainsi qu'on se tient au courant entre les points de rencontre.

## La règle

- **Quand :** à chaque PR fusionnée dans `main`, et avant chaque point de rencontre (H3, H10, H16, H22).
- **Où :** un nouveau fichier `docs/points/AAAA-MM-JJ-<lettre>-<tâche>.md`, ex. `2026-10-10-C-m0.md`.
  Un fichier par personne et par point : on n'édite jamais le fichier d'un autre, donc pas de conflit.
- **Comment :** dans la PR de la tâche (même branche), en copiant le modèle ci-dessous.
- **Lire :** au début de chaque tâche, après `git pull`, lire les points des autres parus depuis le
  dernier. Si une demande vous est adressée, y répondre dans **votre** prochain point (ou en
  commentaire de la PR, si c'est urgent).
- Court : 20 à 40 lignes. Pas de roman, des faits et des questions.

## Modèle

```markdown
# Point <lettre> — <tâche> — <date>

## Fait
- …

## Disponible pour vous
- <fonction / commande / URL> : ce qu'elle fait, comment l'appeler.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| A | … | H3 | oui / non / choix |

## Réponses à vos demandes
- (réponse à la demande de X du <date>) …

## Ensuite
- prochaine tâche ; ce qui me bloque.
```
