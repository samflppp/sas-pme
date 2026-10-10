# Point B (Mouabd19) — veille par flux RSS (M2) — 2026-10-10

## Fait
- **`plateforme/pipeline/veille_rss.py`**, appelé à chaque tour de veille, après PyPI et OSV. Une
  panne de l'un n'empêche pas l'autre.
- **Quand un article alerte :** il emploie un mot d'attaque (malicious, compromised, backdoor,
  steal, typosquat…) **et** nomme un paquet du catalogue en mot entier : `fake-requests` ne vise
  pas `requests`.
  - S'il cite une version (`demo-horodatage 1.2`, `==1.2`, `@1.2`), elle seule est visée.
  - Sinon, s'il parle de PyPI, seules les versions **en attente** du paquet sont visées.
- **Ce que l'alerte donne :** un signal `VEILLE` / **FORT** / `article`, **non structuré**
  (`structure=False`). Le contrat refuse qu'un article bloque, et la politique ne laisse
  qu'un humain approuver : **un article ne débloque jamais**, même s'il le demande (testé).
  - En attente : le signal entre dans la politique à l'analyse, donc la version passe **à revoir**.
    Le LLM le voit aussi.
  - Approuvée, pas encore publiée : la version repasse **à revoir**.
  - Publiée : le signal s'affiche sur la fiche et le journal note `article_version_publiee`.
    **Aucune révocation automatique** sur un simple article : c'est l'humain qui révoque.
- **Chaque article n'alerte qu'une fois** par version, et chaque flux est relu au plus toutes les
  30 min.
- **Flux :** variable `SAS_FLUX` (URL séparées par des virgules), sinon
  `plateforme/pipeline/donnees/flux_rss.txt`.
  - Datadog Security Labs est vérifié ici.
  - Le blog PyPI, Socket et StepSecurity sont bloqués par le proxy de mon environnement, donc à
    vérifier sur AWS. Un flux injoignable est ignoré à ce tour.
- **Essai réel :** sur les 30 articles du flux Datadog, avec 500 paquets populaires au
  catalogue, il n'y a **aucune fausse alerte**.
- **Tests :** 14 nouveaux, chacun cassé une fois ; 373 passent.

## Disponible pour vous
- **A :** rien à changer. Les signaux `article` s'affichent déjà sur la fiche, et la raison cite
  l'article. Pour la page de tableau de bord, l'action de journal `article_version_publiee`
  signale une version **publiée** visée par un article : c'est un candidat à la révocation.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (ou la reprise) | Sur AWS, après `git pull` : `python3 -I -c "import httpx; from plateforme.pipeline import veille_rss as v; [print(u, httpx.get(u, follow_redirects=True, timeout=20).status_code) for u in v.flux()]"`. Me dire quels flux répondent 200. | non | liste des codes |

## Ensuite
- Ma colonne M2 est finie. Il reste la validation du RAG sur AWS (demande du point B-rag). Au
  point H16, on répète la démo complète, puis M3 : la mesure finale à trois colonnes.
