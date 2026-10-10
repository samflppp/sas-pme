# Point B (Mouabd19) — à C : ce qui reste pour clore le M2 — 2026-10-10

## Réponses à C (STEUSSO)
- **(`C-reponses-sam` : C4 et C6)** **Merci, c'est réglé.**
  - **C4, 200 avec `retire: []` :** ok, ton argument tient. La révocation suit maintenant la règle
    de l'inventaire, donc le risque que je voyais (des fichiers ratés) a disparu. Garder un 404
    bloquerait l'admin.
  - **C6 :** ok, rien à ajouter.
- **(`C-reponses-sam` : ordre C1, C2, C3, C5, C7)** **Ok pour cet ordre.**
- **`SAS_CLE_JOURNAL` :** `installer.sh` la tire déjà dans `~/.sas-cle-journal`. Dans mon bloc
  AWS, la ligne `[ -f ~/.sas-cle-journal ] || …` ne fera donc rien : c'est voulu.

## Ce qui te reste pour clore le M2, dans l'ordre
| # | Tâche | Pourquoi | Fini quand |
|---|---|---|---|
| 1 | **C1 : la sandbox ne doit plus devenir aveugle** (`_lire`, plafond de 5 Mo sur `reseau.jsonl`) | sinon la preuve de la démo 3 se contourne | un paquet qui envoie 110 000 requêtes `localhost` avant sa fuite est quand même vu, ou son journal tronqué devient un signal |
| 2 | **C2 : les traces ne doivent plus pouvoir être effacées** (`/journal` en 0777) | même raison | un `trace.jsonl` vidé ou sans événement de fin, écrit par `lancer.sh`, est suspect |
| 3 | **C3 : plus de publication sans signature** (stub `scp` de `publier`) | « rien n'est publié sans signature » (démo 4) | sans `SAS_PASSERELLE_URL`, `publier` lève une erreur ; seul `recepteur` écrit dans le dépôt |
| 4 | **Bloc AWS de B** (point `B-a4-et-aws`, section « Le bloc pour C ») | dernier morceau du M2 de B : RAG et veille RSS validés sur la vraie plateforme | sa sortie est collée dans ton point (N documents, ligne `cite :`, codes HTTP des flux, fiche 1.2 bloquée qui cite le RAG) |
| 5 | **Sauvegardes** (`infra/sauvegarde.sh`, `restic` local, test de restauration) | ta tâche du M2 (`docs/sauvegardes.md`) | effacer la base, la restaurer, puis `verifier_journal()` rend `(True, None)` avec la même `SAS_CLE_JOURNAL` |
| 6 | **C5 : le DNS du VPC** | démo 1 (« le serveur ne parle jamais à Internet ») | sortie de `dig exemple.com` sur le serveur ; s'il répond, `--no-enable-dns-support` puis `dig` à nouveau |
| 7 | C7 : les mineurs | — | si le temps le permet, sinon après H16 |

**Conseil d'ordre :**
- Fais le n° 4 **dès que tu ouvres la plateforme AWS**, même avant C1 : il ne demande que de
  lancer des commandes, et il me débloque.
- Fais le n° 6 dans la même séance (une seule commande).
- Pour tester C1 et C2, je peux t'écrire le petit paquet de démonstration, hors du dépôt, si tu
  veux.

## Ensuite, tous ensemble : le point H16
- On répète une fois la démo complète sur AWS (`demo/script.md`, avec `SAS_SANDBOX_ATTENTE=10`).
- Puis on gèle les fonctions.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Les tâches 1 à 6 ci-dessus ; la sortie du n° 4 et du n° 6 dans ton point | H16 | les sorties ; ok / question |
