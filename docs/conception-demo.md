# Conception — la plateforme comme scène unique de la démo (A, 2026-10-11)

Décidée avec Sam le 2026-10-11. Pendant la démo, on ne quitte jamais la plateforme : on demande un
paquet, on le voit traverser la pipeline et arriver sur le serveur, on parcourt le catalogue. Sam
fait tout le chantier lui-même, y compris dans les dossiers de B (`plateforme/pipeline/`) et de C
(`passerelle/`, `infra/`) ; les points de A le signalent à B et à C.

## 1. Ce qu'on voit

Même langage visuel que pipelad.tech : polices Selawik et JetBrains Mono auto-hébergées, accent
ambre, tuiles à filet d'un pixel, barre latérale à la manière de Power BI. Aucune ressource
extérieure, aucun cadre JavaScript.

| Page | Contenu |
|---|---|
| **Demandes** | Formulaire (écosystème, nom) et liste des demandes avec leur état. Une demande envoyée ouvre la page **Direct** sur ce paquet. |
| **Catalogue** | Arborescence à la GitHub : `pypi/`, `npm/`, `images/` ; un paquet, ses versions ; une version, ses fichiers (archives, manifeste signé, verdict). À droite, la « fiche » en tête de dossier : état, raison, version amont encore en attente. |
| **Direct** | Deux panneaux côte à côte (l'un sous l'autre sur mobile) : **Serveur** et **Pipeline**, mis à jour en direct. |
| Tableau de bord, file d'attente, inventaire, journal, comptes, fiche | Restylés, mêmes données. |

### Panneau Serveur : vrai, lu à la passerelle
Il met en forme de terminal les **vraies** requêtes du serveur, lues dans le journal d'accès de
pypiserver (celui que l'inventaire lit déjà) : `GET /simple/<nom>/`, puis le téléchargement de
l'archive, avec heure et IP. Sous la dernière ligne : la version installée, la version amont qui
attend encore (et combien de temps), et « pypi.org : jamais contacté ». Rien n'y est inventé : une
ligne absente du journal n'est pas affichée.

Pour qu'une demande déclenche une vraie installation sans quitter la plateforme, le serveur de
démo fait tourner un petit service (`infra/serveur/`) : il lit à la passerelle les installations
demandées, **signées par la plateforme** (Ed25519, même clé que les publications), et lance
`pip install` vers la passerelle. Un nom non signé ou mal formé n'est jamais exécuté.

### Panneau Pipeline : les étapes, et l'IA mot à mot
Une ligne par étape, avec son état et sa durée : demande, délai de 3 jours, téléchargement,
statique, sandbox, IA, politique, signature, publication. Dans l'étape IA, l'explication du LLM
s'écrit mot à mot. La dernière ligne rappelle que la décision vient du code (politique), pas du LLM.

## 2. Comment

- **Étapes** : `traiter` (B) reçoit un rappel facultatif `suivi(sujet, etape, etat, detail)` ; chaque
  étape est aussi écrite au journal chaîné (action `etape`), donc auditable et rejouable.
- **LLM en flux** : `llm.analyser` lit Ollama en `stream: true`. Les morceaux passent par `suivi` et
  ne sont gardés qu'en mémoire ; la réponse complète est validée par le même schéma qu'avant. Un
  flux coupé donne le même résultat qu'une panne (rien), comme aujourd'hui.
- **Transport** : Server-Sent Events (`/direct/flux`), un `EventSource` dans `direct.js` ; repli en
  rechargement si le navigateur n'a pas `EventSource`.
- **Passerelle** (C) : `GET /v1/acces` (TLS mutuel, comme `/v1/inventory`) rend les dernières lignes
  du journal d'accès, déjà découpées ; `POST /v1/installer` reçoit une demande d'installation signée
  et la range ; `GET /v1/installations` la rend au service du serveur.
- **Images Docker** : aucune pipeline ne les analyse. Elles viennent d'un fichier tenu à la main
  (`plateforme/web/images-agreees.json` : nom, digest, date, qui) et sont affichées comme telles :
  « ajoutée à la main, non analysée par la pipeline ».

## 3. Découpage (une PR chacune)

1. Gabarit, barre latérale, styles et polices (A).
2. Catalogue en arborescence et images Docker (A).
3. Étapes et LLM en flux (dossier de B).
4. Page Direct, panneau Pipeline, page Demandes (A).
5. Passerelle `/v1/acces`, `/v1/installer`, service du serveur (dossier de C) ; panneau Serveur (A).

Chaque PR : test vu rouge, code, test vert, code cassé une fois pour voir le test tomber.
