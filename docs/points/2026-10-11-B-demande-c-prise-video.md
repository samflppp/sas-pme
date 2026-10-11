# Point B (Mouabd19) — demande à C : base neuve et nouveaux paquets pour la vidéo — 2026-10-11

Mouabd19 tourne la vidéo maintenant. Il demande deux choses :
- **repartir sur une base neuve** ;
- **de nouveaux paquets pour chaque cas**, ceux de `C-pret-video` étant déjà connus.

## Fait (`demo/paquets/`, mon dossier)
Les fausses sources servent maintenant le trio sous **n'importe quel numéro de prise** (1 à 999).
`demo-piege-2` est un paquet jamais vu, au même contenu que `demo-piege`. Chaque prise rejoue
donc toute l'analyse, même sans base neuve.
- Tests : 18 cas (3 couleurs × 2 écosystèmes × 3 prises), plus un numéro invalide refusé. J'ai
  cassé le code une fois : les tests sont passés au rouge.
- Vraie sandbox : `demo-piege-2` et `demo-npm-piege-2` lisent le leurre et appellent l'attaquant,
  `demo-npm-sain-2` reste propre. Suite complète : 761 verts.

## À faire sur la plateforme (C), maintenant
```bash
cd ~/sas-pme && git pull origin main
pkill -f "uvicorn plateforme.web.app"
mkdir -p ~/bases-archivees && d=$(date +%H%M%S)
for f in sas.db sas.db-wal sas.db-shm; do [ -f "$f" ] && mv "$f" ~/bases-archivees/"$f.$d"; done
~/h16.sh      # relance faux PyPI, faux npm et web (SAS_PYPI_URL, SAS_NPM_URL)
curl -s localhost:8081/pypi/demo-piege-2/json | head -c 100; echo
curl -s localhost:8082/demo-npm-piege-2 | head -c 100; echo
```
- Si `~/h16.sh` fixe `SAS_DB` ailleurs, archiver ce fichier-là.
- Le faux PyPI et le faux npm **doivent être relancés** (`~/h16.sh` le fait) pour connaître les
  numéros de prise.
- Recréer `dev` dans « Comptes » si la vidéo l'utilise. Prévenir Mouabd19 quand c'est prêt.

## Les paquets à demander, par prise
| Prise | pypi vert | pypi orange | pypi rouge | npm vert | npm orange | npm rouge |
|---|---|---|---|---|---|---|
| essai | `demo-sain-1` | `demo-a-revoir-1` | `demo-piege-1` | `demo-npm-sain-1` | `demo-npm-a-revoir-1` | `demo-npm-piege-1` |
| vidéo | `demo-sain-2` | `demo-a-revoir-2` | `demo-piege-2` | `demo-npm-sain-2` | `demo-npm-a-revoir-2` | `demo-npm-piege-2` |
| reprise | `demo-sain-3` | `demo-a-revoir-3` | `demo-piege-3` | `demo-npm-sain-3` | `demo-npm-a-revoir-3` | `demo-npm-piege-3` |

Pour une prise de plus, prendre le numéro suivant. Compter environ 70 s d'analyse par paquet.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Les commandes ci-dessus, puis dire à Mouabd19 que la base neuve est prête | vidéo | prêt |
