# Point B (Mouabd19) — essai local du déroulé H16 — 2026-10-11

## Fait
J'ai joué le déroulé H16 en local, hors AWS, sur `main` (avec la règle d'ancrage du LLM, PR #69).
Un script pilotait le web comme un admin et chronométrait chaque étape.

**Ce qui tournait, et comme en vrai :**
- le web et le pipeline (`SAS_DELAI=60`, `SAS_TRAITEMENT_INTERVALLE=10`, `SAS_SANDBOX_ATTENTE=10`) ;
- le faux PyPI ;
- la **vraie sandbox Docker** (réseau interne, piège, leurres, `strace`) ;
- une **passerelle locale** : `passerelle.recepteur` en TLS mutuel, avec la vraie signature
  Ed25519.

Clés et certificats ont été tirés pour l'essai, hors du dépôt.

**Ce qui manquait :**
- **le LLM et le RAG** : pas d'Ollama ici. Le pipeline l'a noté au journal et a continué ;
- le relais d'API, pypiserver et le serveur. Ils sont déjà vérifiés par C sur AWS.

| Étape | Résultat | Temps (sans LLM) |
|---|---|---|
| Demander `demo-horodatage` → 1.0 | **publiée**, signée, dans le dépôt de la passerelle | 20 s |
| 2. la 1.1 sort | **publiée** ; aucun signal ; sandbox propre (11,5 s) | 78 s après sa sortie (60 s de délai) |
| 3. la 1.2 piégée sort | **bloquée** : `exfiltration` (statique) et `lit_leurre` (sandbox), avec DNS `collecte.attaquant-demo.invalid`, connexion vers le piège, `~/.aws/credentials` ouvert ; plus `acces_secrets` et `mainteneur_change` | 80 s après sa sortie |
| 7. la 1.3 sort | **à revoir**, sur un seul signal : `domaine_suspect` (ngrok) ; sandbox propre | 78 s après sa sortie |
| 7. l'admin clique « Bloquer » | 303, **bloquée** ; second clic « Approuver » : **400**, l'état ne bouge pas | immédiat |
| 4. publication forgée (mauvaise clé) | **401 « signature invalide »** ; et sans certificat client, la passerelle coupe la connexion | immédiat |
| révocation de la 1.1 depuis l'interface | 303, **révoquée** ; ses deux archives sont retirées du dépôt de la passerelle | immédiat |
| fin | tableau de bord « Journal intact » ; `verifier_journal()` = `(True, None)`, 33 entrées ; pas une erreur dans le journal du web | — |

## Ce que l'essai apprend
- **Le déroulé du script H16 tient de bout en bout**, 1.3 et décision humaine comprises.
- **Minutage :** compter environ 80 s par version entre sa sortie et son état final, **plus le
  LLM** (de 50 à 60 s sur CPU d'après C), soit environ 2 min 20 s par version. Pour tenir les
  3 minutes, l'avis de C tient : lancer 1.1 et 1.2 avant de parler.
- **Sécurité par défaut vérifiée par accident :**
  - au premier essai, l'image `sas-sandbox:2` n'a pas pu être construite (le miroir Debian est
    bloqué ici) ;
  - le pipeline a mis la version **« à revoir » (« analyse impossible »)** au lieu de la publier
    sans analyse. C'est le bon comportement ;
  - **C :** gardez donc l'image construite d'avance sur la plateforme (ton § 3), car le jour J un
    miroir lent mettrait toutes les versions « à revoir ».
- **Non vérifié ici :**
  - l'alerte de `/inventaire` (sans pypiserver, la 1.1 n'a jamais été téléchargée) ;
  - les citations du RAG ;
  - l'effet de la règle d'ancrage sur un vrai LLM.

  C l'a vu sur AWS pour les deux premiers. Le troisième se verra au H16 sur certifi et idna.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Au redéploiement : construire `sas-sandbox:2` **avant** la répétition, pas à la première analyse | H16 | ok |
