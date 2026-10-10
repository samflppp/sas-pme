# Point C (STEUSSO) — préparer le point H16 — 2026-10-11

## Fait
- **M2 de C fini** (PR #62) : sandbox v2, relais d'API, sauvegardes, puis C1, C2, C3, C5 et C7
  demandés par B. Les sorties AWS sont dans `2026-10-10-C-fin-m2.md`.
- **Infra AWS en marche et vérifiée** : `verifier_h3` donne 6 OK sur 6, `verifier_m1` est vert.
- **La démo 1.2 a déjà été passée de bout en bout avec le RAG**, depuis `~/sas-c-e2e` sur la
  plateforme : la 1.2 est bloquée, et la fiche cite CWE-522 et T1552.005.
- J'ai lu `A-correctifs-a5` et `A-page-inventaire`. Rien ne me vise. J'ajoute le contrôle
  « 1.2 révoquée → alerte dans `/inventaire` » au déroulé ci-dessous.

## Le point H16 (`docs/roadmap.md`)
On répète une fois la démo complète sur AWS, à trois, puis on gèle les fonctions.

**1. Avant : chacun confirme dans son point que sa partie est sur `main`.**
- **A :** dire si A1 à A4 (`A-reponse-b`) sont tous fusionnés, ou lesquels restent.
- **B :** passer `attendu=Etat.A_REVOIR` dans `decision_humaine` (demande de A).
- **B :** traiter `JOURNAL_TRONQUE` (en tête de `requetes_dns`) et `TRACES_EFFACEES` (en tête de
  `processus`) comme des signaux sandbox **forts** au moins. La sandbox les émet depuis la PR #62.

**2. A : écrire la section « H16 » de `demo/script.md`.** Elle reprend le déroulé H10, avec :
- dans le § 3, `export SAS_SANDBOX_ATTENTE=10` : sans lui, chaque analyse attend 60 s de plus ;
- en ouverture, le tableau de bord (« 1 bloquée, 0 à revoir, journal intact ») ;
- à l'étape 3, l'explication du LLM qui cite le RAG (`refs_rag` sur la fiche) ;
- ce qui est nouveau au M2 :
  - la **révocation** depuis l'interface, puis la 1.2 (ou une version publiée) en alerte dans
    **`/inventaire`** ;
  - la **décision humaine** sur une version à revoir ;
  - le **relais d'API**, depuis le serveur :
    `curl -x http://passerelle:3128 https://api.github.com` passe, alors que la même commande
    vers `https://pypi.org` est refusée (403).
- un minutage réaliste : sur CPU, le LLM met de 50 à 60 s par version, et la sandbox 10 s.

**3. C : préparer la plateforme le jour même** (environ 15 min) :
- redéployer `main` dans `~/sas-pme` ; l'index `rag_index/` n'est pas dans l'archive, il reste ;
- reconstruire l'image `sas-sandbox:2`, pour qu'elle ait C1 et C2 ;
- lancer le web avec une **base neuve**.

**4. Pendant :** chacun regarde sa partie et note ce qui casse et le temps qu'elle prend.

**5. Après :**
- chacun écrit son point H16 ;
- on décide des coupes : je propose npm et WireGuard **hors** démo ;
- on gèle les fonctions et on passe au M3 :
  - A : deck et fiche de défense ;
  - B : mesure finale ;
  - C : vidéo, schéma réseau, diapositive « plateforme compromise ».

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| A (Sam) | Dire si A1 à A4 sont sur `main` ; écrire la section H16 de `demo/script.md` (§ 2 ci-dessus) | H16 | fait / question |
| B (Mouabd19) | `attendu=Etat.A_REVOIR` dans `decision_humaine` ; `JOURNAL_TRONQUE` et `TRACES_EFFACEES` en signaux forts | H16 | fait / question |
| A, B | Donner une heure pour la répétition à trois ; je redéploie 15 min avant | H16 | une heure |
| A, B | D'accord pour couper npm et WireGuard de la démo ? | H16 | ok / non |

## Ensuite
- En attendant H16 : une répétition à blanc seul sur AWS, pour noter le minutage ; puis le M3
  (vidéo, schéma réseau).
