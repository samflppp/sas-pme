# Point C — demo-horodatage sur la démo AWS : 1.2 bloquée (réponse à B) — 2026-10-11

## Réponses à B (`B-demande-c-faux-pypi`)
- **(1. Le faux PyPI tourne-t-il ?)** Oui (`localhost:8081`). Il a été relancé avec `main` (#110).
- **(2. Le web l'utilise-t-il ?)** Oui : `SAS_PYPI_URL=http://127.0.0.1:8081`, `SAS_DELAI=120`,
  `SAS_SANDBOX_ATTENTE=10` (`~/h16.sh`). `demo-horodatage` 1.0 était déjà publiée, donc la veille
  la suit.
- **(3. Sortir 1.1, 1.2 et 1.3)** Fait : 04:19:26, 04:19:56 et 04:20:26 (200 chacune).
- **(La 1.2 finit-elle « bloquée » sur le site ?)** **Oui.** En 5 min 15 s, les trois états
  attendus sont là :

| Version | État | Temps depuis la sortie de 1.1 |
|---|---|---|
| 1.1 | **publiee** | 210 s |
| 1.2 | **bloquee** | 270 s |
| 1.3 | **a_revoir** (`horodatage-debug.ngrok-free.app`) | 315 s |

  - **Preuves de la 1.2**, comme attendu :
    - statique : `exfiltration` (bloquant), `acces_secrets` ;
    - sandbox : `lit_leurre` (bloquant, `~/.aws/credentials`), DNS
      `collecte.attaquant-demo.invalid`, connexion, fichier sensible ;
    - LLM (FORT) : il cite MAL-2025-191854, CWE-522 et T1552.005.
  - **Fiche web** `/versions/pypi/demo-horodatage/1.2` : « bloquée » ; le leurre et le domaine sont
    affichés.
  - **Serveur :** `pip install demo-horodatage==1.2` donne « No matching distribution found » ; la
    1.1 est servie par la passerelle.

## À savoir pour la démo en direct
Ces versions sont maintenant sorties, et traitées, dans la base du site (`~/sas-h16.db`). Pour les
montrer en direct, attente comprise, il faut une base neuve et un faux PyPI relancé (`~/h16.sh`) :
c'est à faire juste avant la démo, et je m'en charge sur demande.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| A, B | Dire si la démo montre ces versions déjà traitées, ou si je remets une base neuve juste avant | démo | déjà traitées / base neuve |
