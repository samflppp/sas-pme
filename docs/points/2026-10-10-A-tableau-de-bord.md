# Point A (Sam) — tableau de bord (M2) — 2026-10-10

## Fait
- **`GET /tableau-de-bord`** (`plateforme/web/app.py`, gabarit `tableau.html`), premier lien du
  menu, ouvert à tout compte connecté :
  - **compteurs** : une case par état (`nouvelle` à `revoquee`, même à 0, dans l'ordre du cycle de
    vie) et le total ;
  - **à trancher** : les versions `a_revoir`, avec leur raison et un lien vers la fiche, où l'admin
    décide ;
  - **derniers blocages** : les 5 versions bloquées ou révoquées les plus récentes, avec leur raison ;
  - **journal** (admin seulement, comme la page `/journal`) : nombre d'entrées et chaîne de hash
    vérifiée à chaque affichage, « Journal intact » ou « Journal falsifié », avec le numéro de
    l'entrée qui casse.
- Rien de neuf en base : tout vient des méthodes existantes (`lister_versions`,
  `lister_avec_raison`, `compter_journal`, `verifier_journal`).
- **10 tests** (`tests/plateforme/test_tableau_de_bord.py`), vus rouges avant le code, puis quatre
  mutations vues rouges : ordre des blocages, journal montré à un dev, vérification de la chaîne
  sautée, états à 0 absents. Suite complète : 426 verts, 4 sautés.

## Pour la démo
- Le tableau de bord est une bonne ouverture : « 1 bloquée, 0 à revoir, journal intact ». Je l'ajoute
  au script H16 quand on le répète.

## Demandes
Aucune.
