# Point A (Sam) — révocation depuis l'interface (M2) — 2026-10-10

## Fait
- **`POST /revocation`** (`plateforme/web/app.py`), admin seulement :
  - formulaire sur la fiche d'une version **publiée** : une raison obligatoire (500 caractères au
    plus), puis le bouton « Révoquer cette version » ;
  - la passerelle d'abord : `signature.revoquer(eco, nom, version, raison)` (C) retire l'archive.
    Ensuite seulement, la version passe à `revoquee` par `base.changer_etat`. La raison est
    « admin : <raison> », et le journal chaîné dit qui a révoqué et pourquoi ;
  - si la passerelle refuse (`PublicationRefusee`) ou est en panne (réseau, ssh), la version reste
    `publiee`. L'échec est journalisé (`revocation_echouee`) et dit sur la fiche (502), et le
    bouton reste là pour réessayer ;
  - une version qui n'est pas publiée : 400, sans appel à la passerelle. Un dev : 403. Une version
    inconnue : 404.
- `creer_app(..., revoquer=None)` : `signature.revoquer` est importé au premier clic, et les tests
  passent un faux.
- **13 tests** (`tests/plateforme/test_revocation_web.py`), vus rouges avant le code, puis trois
  mutations vues rouges : sans le contrôle d'état, sans l'appel à la passerelle, et avec le
  formulaire montré à un dev. Suite complète : 416 verts, 4 sautés.

## Choix à valider
- **Seule une version `publiee` se révoque.** Une version `approuvee` pas encore publiée (passerelle
  en panne) n'a rien à retirer. La bloquer demande une autre action, hors de ce périmètre.
- Une version révoquée ne revient pas. Une nouvelle version passe par le circuit normal.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C | Confirmer que `signature.revoquer` en mode signé (`SAS_PASSERELLE_URL`) retire bien wheel **et** sdist, et répond 200 même si l'archive était déjà absente. | démo de révocation | ok |
| B | Rien à changer côté pipeline : `traiter` ne republie que les versions `approuvee`, donc une version `revoquee` n'est jamais republiée. À confirmer. | — | ok |
