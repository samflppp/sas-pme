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

## Démo prête (base neuve, 2026-10-11 04:28)
- L'ancienne base est archivée dans `~/bases-archivees/` sur la plateforme, pas effacée. Le web
  repart sur une base neuve, et le faux PyPI sur la seule 1.0.
- Préparation du script faite : `requests` et ses 4 dépendances, puis `demo-horodatage` 1.0, sont
  **publiés** en 345 s, sans aucune version « à revoir ».
- Pour la démo : sortir 1.1, 1.2 et 1.3 sur la plateforme
  (`curl -X POST localhost:8081/demo/publier/demo-horodatage/<v>`). Il faut compter environ 5 min
  pour les trois états (mesuré plus haut).
- Le compte `admin` garde le même mot de passe. Les autres comptes de l'ancienne base sont à
  recréer.
