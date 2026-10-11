# Point B (Mouabd19) — demande à C : mettre la plateforme à jour avant la vidéo — 2026-10-11

Mouabd19 veut tourner la vidéo de démo. Deux changements sont dans `main` et pas encore sur AWS :
- **#114**, le trio vert / orange / rouge pour PyPI et npm (point `B-trio-demo`) ;
- **#115**, les croix rouges de l'IA à la publication pour une version bloquée (point
  `B-croix-bloquee`).

## Demande à C (STEUSSO), sur la plateforme
```bash
cd ~/sas-pme && git pull origin main
# faux PyPI relancé (il doit connaître le trio), faux npm lancé (neuf, port 8082)
pkill -f demo/paquets/faux_pypi.py; .venv/bin/python demo/paquets/faux_pypi.py > ~/faux_pypi.log 2>&1 &
pkill -f demo/paquets/faux_npm.py;  .venv/bin/python demo/paquets/faux_npm.py  > ~/faux_npm.log 2>&1 &
curl -s localhost:8081/pypi/demo-piege/json | head -c 120; echo
curl -s localhost:8082/demo-npm-piege | head -c 120; echo
```
Puis relancer `uvicorn` avec les variables habituelles, **plus** :
```bash
export SAS_PYPI_URL=http://127.0.0.1:8081 SAS_NPM_URL=http://127.0.0.1:8082
```

## Vérification
- Sur le site, demander `demo-piege` (pypi). Il doit finir **bloqué**, avec des croix rouges
  de « IA locale » à « Signature et publication ».
- Si tu as le temps, faire de même pour les cinq autres paquets du tableau du point `B-trio-demo`.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Les commandes ci-dessus, puis dire quand le site est prêt pour la vidéo | vidéo | prêt / capture |
