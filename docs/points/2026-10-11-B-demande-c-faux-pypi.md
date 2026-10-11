# Point B (Mouabd19) — demande à C : lancer le faux PyPI sur la démo AWS — 2026-10-11

Constat de Mouabd19 : sur demo.pipelad.tech, aucune version n'a fini **bloquée**. C'est normal
avec de vrais paquets : seule une preuve d'attaque bloque (leurre lu en sandbox, exfiltration,
avis OSV ou retrait du registre). Pour l'étape 3 de la démo, il faut la version piégée
`demo-horodatage` 1.2, servie par le faux PyPI (`demo/paquets/faux_pypi.py`).

## Demande à C (STEUSSO), sur la plateforme
1. **Le faux PyPI tourne-t-il ?**
   ```bash
   curl -s localhost:8081/pypi/demo-horodatage/json | head -c 300
   ```
   S'il ne répond pas, le lancer depuis le dépôt à jour :
   ```bash
   cd ~/sas-pme && .venv/bin/python demo/paquets/faux_pypi.py > ~/faux_pypi.log 2>&1 &
   ```
2. **Le web l'utilise-t-il ?** `uvicorn` doit avoir été lancé avec
   `SAS_PYPI_URL=http://127.0.0.1:8081`, et `SAS_DELAI=120` pour la démo (`demo/script.md`).
   Sinon, le relancer avec ces variables, plus les autres variables habituelles.
3. **Faire sortir la version piégée :**
   ```bash
   curl -X POST localhost:8081/demo/publier/demo-horodatage/1.2
   ```
   Si ce n'est pas déjà fait, sortir aussi 1.1 (saine) et 1.3 (à revoir), pour toute la démo.

## Vérification attendue
- Sur le site : « Demandes », `pypi`, `demo-horodatage`. La 1.2 attend son délai, puis elle
  finit **bloquée**. Preuves attendues : le leurre `~/.aws/credentials` lu en sandbox, une
  requête DNS vers `collecte.attaquant-demo.invalid`, l'exfiltration repérée en statique.
- Sur le serveur : `pip install demo-horodatage==1.2` échoue (introuvable sur la passerelle).

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Étapes 1 à 3 ci-dessus, puis dire si la 1.2 finit « bloquée » sur le site | démo, étape 3 | oui / capture de la fiche |
