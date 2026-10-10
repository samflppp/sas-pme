# Journaux d'avancement

Un fichier par personne : `a.md` (Sam), `b.md` (Mouabd19), `c.md` (STEUSSO). **Chacun n'écrit que
dans le sien**, donc il n'y a jamais de conflit de fusion. Ce système remplace aussi les « points »
(`docs/points/`), dont il reprend le tableau des demandes.

## Quand
- **Au début d'une tâche**, après `git pull` : lire les journaux des deux autres, pour savoir ce qui
  est fait, en cours ou attendu de soi. Ne pas refaire leur travail, et signaler à l'utilisateur
  les demandes qui le visent.
- **À la fin d'une tâche**, dans la même PR que le code : ajouter une entrée en haut de son journal.
- **Avant chaque point de rencontre** (H3, H10, H16, H22) : chacun a une entrée à jour.

## Format d'une entrée (la plus récente en haut)

```markdown
## AAAA-MM-JJ — <tâche> (<branche>, PR <lien>)
- **Fait :** ce qui marche maintenant, en 2 à 5 points.
- **Disponible pour vous :** fonction, commande ou URL, et comment l'appeler.
- **Demandes :**

  | À | Demande | Bloquant pour | Réponse attendue |
  |---|---|---|---|
  | A | … | H3 | oui / non / choix |

- **Réponses à vos demandes :** (à la demande de X du <date>) …
- **En cours / suite :** ce que je fais ensuite, pour que personne ne le prenne.
```

Court et factuel : le détail est dans la PR et le code. Une section vide s'omet.
