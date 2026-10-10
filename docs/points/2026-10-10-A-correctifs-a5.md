# Point A (Sam) — correctifs A5 de la relecture de B — 2026-10-10

## Fait
- **Origine des POST (CSRF).** Tout POST dont l'en-tête `Origin` (ou, à défaut, `Referer`) ne
  désigne pas l'hôte de la requête (`Host`) est refusé (403). Le refus est journalisé
  (`origine_refusee`, avec le chemin et l'origine). `Origin: null` est refusé, et un autre port de
  la même machine aussi : c'est le cas que `same_site="strict"` laissait passer derrière le tunnel
  de la démo. La connexion est couverte (pas de connexion forcée).
  - Sans `Origin` ni `Referer`, la requête passe : ce n'est pas un navigateur (curl, script), donc
    il n'y a pas de CSRF possible. Les navigateurs actuels envoient toujours `Origin` sur un POST.
- **Changer son mot de passe coupe les autres sessions.** `Compte.generation` change à chaque
  changement de mot de passe : c'est le début du sel scrypt, tiré à nouveau à chaque fois, qui ne
  dit rien du mot de passe. La session la garde à la connexion ; une session dont la génération
  diffère est coupée à la requête suivante. La session qui a fait le changement reste ouverte.
  Aucune colonne ajoutée : une base existante n'a rien à migrer. Les sessions ouvertes avant ce
  correctif devront se reconnecter une fois.
- **`SAS_ADMIN_MOTDEPASSE` soumis à `MDP_MIN` (12).** Sur une base sans compte, une valeur plus
  courte empêche de démarrer (`RuntimeError`) au lieu de créer un admin faible. Une fois la base
  créée, la variable reste ignorée, comme avant. `demo/script.md` le dit.
- 16 tests (`tests/plateforme/test_sessions_web.py`), dont 9 vus rouges avant le code. Mutations
  vues rouges : origine toujours acceptée, `Origin` ignoré, génération non vérifiée, session
  courante non mise à jour, `MDP_MIN` non vérifié. Suite complète : 477 verts, 7 sautés.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| — | Aucune. Pour la démo : ouvrir l'interface par l'adresse du tunnel, pas par une autre adresse qui mènerait au même serveur. | — | — |
