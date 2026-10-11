# Point B (Mouabd19) — demande à C : livraison au jury, version finale sur un site vierge — 2026-10-11

Mouabd19 fait la démo devant le jury. Il veut :
- **la version finale en ligne** (#127, point `B-version-finale`) ;
- **un site vierge** : aucune demande, aucune version, aucun paquet servi ni installé avant la démo.

## 1. Plateforme : code final et base neuve
```bash
cd ~/sas-pme && git pull origin main                 # #127 et suivantes
pkill -f "uvicorn plateforme.web.app"
mkdir -p ~/bases-archivees && d=$(date +%Y%m%d-%H%M%S)
for f in ~/sas-h16.db ~/sas-h16.db-wal ~/sas-h16.db-shm; do [ -f "$f" ] && mv "$f" ~/bases-archivees/"$(basename $f).$d"; done
```
La base du site est `~/sas-h16.db`, d'après ton point `C-base-neuve-video`. L'ancienne est
archivée, jamais effacée : le journal ne s'efface pas.

## 2. Passerelle : dépôts et journaux vierges (sinon « Inventaire » montre les anciens paquets)
La page « Inventaire » lit la passerelle, pas la base : sans cette étape, elle listerait les
paquets des essais.
```bash
sudo systemctl stop recepteur verdaccio pypiserver
d=$(date +%Y%m%d-%H%M%S); sudo mkdir -p /var/lib/sas-archives/$d
# pip : garder la seule roue de pip (le serveur en a besoin pour s'amorcer), archiver le reste
sudo find /srv/pypi/packages -maxdepth 1 -type f ! -name 'pip-*.whl' -exec mv -t /var/lib/sas-archives/$d {} +
# npm : archiver le stockage de Verdaccio (le compte « recepteur », dans htpasswd, reste)
sudo mv /var/lib/verdaccio/storage /var/lib/sas-archives/$d/verdaccio-storage
sudo install -d -o verdaccio -g verdaccio -m 700 /var/lib/verdaccio/storage
# journaux d'accès et registre du récepteur : archivés, puis vides (mêmes droits)
for f in /var/lib/sas/pypiserver-acces.log /var/lib/sas/verdaccio.log /var/lib/sas-recepteur/registre.txt; do
  [ -f "$f" ] && sudo cp -p "$f" /var/lib/sas-archives/$d/ && sudo truncate -s 0 "$f"
done
sudo systemctl start pypiserver verdaccio recepteur
```
- Les nonces (`/var/lib/sas-recepteur/nonces.txt`) restent : un ancien manifeste ne doit
  jamais être rejoué.
- **Si le serveur s'amorce autrement que par `pip-*.whl`**, garde aussi ce fichier. Au moindre
  doute, saute l'étape 2 : la démo marche quand même, seul l'inventaire montrera les anciens
  paquets.

## 3. Serveur : rien d'installé
```bash
~/app/bin/pip freeze | grep -E '^(demo|requests|idna|certifi|urllib3|charset)' | cut -d= -f1 | xargs -r ~/app/bin/pip uninstall -y
rm -rf ~/node_modules ~/package.json ~/package-lock.json 2>/dev/null
sudo rm -f /var/lib/sas-agent/attente.json      # aucun pip en attente d'une ancienne demande
```
`/var/lib/sas-agent/dernier` et `nonces` restent : l'agent ne rejoue rien.

## 4. Relancer et vitrine
```bash
~/h16.sh                                         # web, faux PyPI, faux npm, sur une base vide
```
Puis, depuis ton poste, `infra/aws/domaine.sh` : la vitrine finale (#127).

## Vérification (avant de prévenir Mouabd19)
- **Demandes**, **Catalogue**, **File d'attente**, **Inventaire** et **Journal** sont vides
  (le journal ne garde que la création du compte et ta connexion).
- `https://demo.pipelad.tech/docs` répond 404, et le menu affiche « Paquets ».
- `https://pipelad.tech` affiche « Accéder à la plateforme » et 80 % (103 sur 128).
- Comptes : `admin` (même mot de passe) ; recréer `dev` si Mouabd19 l'utilise.
- **Ne rien demander** sur le site après ça : la première demande doit être celle du jury.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Étapes 1 à 4, puis la vérification ; prévenir Mouabd19 | démo devant le jury | prêt |
