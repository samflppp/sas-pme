# Point B (Mouabd19) — demande à C : une base neuve avant chaque prise de la vidéo — 2026-10-11

Mouabd19 veut l'animation complète de la page Direct à chaque demande de la vidéo. Deux obstacles :
- **Le journal ne s'efface pas**, c'est voulu (journal append-only, chaîné). Aucun bouton
  « vider » n'existe, et il n'en faut pas.
- **Un paquet déjà demandé n'est jamais ré-analysé** : le redemander montre l'ancien résultat,
  sans animation.

La solution est celle que tu as déjà appliquée (`C-demo-horodatage-aws`) : **une base neuve avant
chaque prise**, l'ancienne archivée, jamais effacée.

## À faire sur la plateforme, avant chaque prise
```bash
cd ~/sas-pme
# 1. arrêter le web
pkill -f "uvicorn plateforme.web.app"
# 2. archiver la base (celle de SAS_DB dans ~/h16.sh, ici sas.db) et ses fichiers annexes
mkdir -p ~/bases-archivees && d=$(date +%H%M%S)
for f in sas.db sas.db-wal sas.db-shm; do [ -f "$f" ] && mv "$f" ~/bases-archivees/"$f.$d"; done
# 3. relancer les fausses sources (état de départ) puis le web
pkill -f demo/paquets/faux_pypi.py; .venv/bin/python demo/paquets/faux_pypi.py > ~/faux_pypi.log 2>&1 &
pkill -f demo/paquets/faux_npm.py;  .venv/bin/python demo/paquets/faux_npm.py  > ~/faux_npm.log 2>&1 &
~/h16.sh        # mêmes variables, avec SAS_PYPI_URL et SAS_NPM_URL (point B-demande-c-maj-video)
```
- Si `SAS_DB` pointe ailleurs que `sas.db`, archiver ce fichier-là.
- Le compte `admin` est recréé avec le même mot de passe. Recréer `dev` dans « Comptes » si la
  vidéo l'utilise.
- La passerelle garde ce qui est déjà publié. Ce n'est pas gênant : republier la même version
  est sans effet.

## Déroulé conseillé
1. Base neuve, puis une **prise d'essai** avec les six paquets (`B-trio-demo`).
2. Base neuve à nouveau, puis la **vraie prise**, sans demander deux fois le même paquet.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Base neuve avant chaque prise (commandes ci-dessus) ; prévenir Mouabd19 quand c'est prêt | vidéo | prêt |
