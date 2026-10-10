# Script de démo (A)

## H3 — preuve de vie (atteint le 2026-10-10, 5 OK sur 5 : `docs/points/2026-10-10-C-h3-ok.md`)

But (`docs/roadmap.md`, M0) : une personne demande `requests` dans le web ; la plateforme le
télécharge, l'approuve (politique déterministe : aucun signal fort) et le copie sur la passerelle ; sur le serveur,
`pip install requests` marche alors que `curl https://pypi.org` échoue.

### 1. Infra (C)

Depuis le poste de STEUSSO, voir `infra/README.md` : `creer.sh`, puis `installer.sh`. La région se
règle dans `infra/aws/config.env` (us-east-1 pour le compte du workshop) ; la plateforme est sur
CPU (`c7i.4xlarge`).

### 2. Déployer l'application sur la plateforme

Depuis la racine du dépôt, sur un poste qui a `infra/secrets/ssh_config` (celui de C) :

```bash
git archive --format=tar.gz -o /tmp/sas-pme.tar.gz main
scp -F infra/secrets/ssh_config /tmp/sas-pme.tar.gz sas-plateforme:
ssh -F infra/secrets/ssh_config sas-plateforme 'rm -rf ~/sas-pme && mkdir ~/sas-pme \
  && tar xzf sas-pme.tar.gz -C ~/sas-pme && cd ~/sas-pme \
  && python3 -m venv .venv && .venv/bin/pip install -q -e .'
```

`git archive` évite de mettre un accès au dépôt privé sur la machine.

### 3. Lancer le web (et donc `traiter()` en tâche de fond)

```bash
ssh -F infra/secrets/ssh_config sas-plateforme
cd ~/sas-pme
export SAS_DB=~/sas.db SAS_ARCHIVES=~/archives
export SAS_ADMIN_MOTDEPASSE='<à choisir>'  # ne sert qu'au premier lancement (base neuve)
export SAS_PASSERELLE_SSH=ubuntu@10.42.2.10 SAS_PASSERELLE_CLE=~/.ssh/sas_passerelle
export SAS_TRAITEMENT_INTERVALLE=10        # démo : on voit les états changer vite
.venv/bin/uvicorn plateforme.web.app:app --host 127.0.0.1 --port 8000
```

Le web n'écoute que sur la plateforme elle-même. On y accède par un tunnel SSH, sans ouvrir de
port ni gérer de certificat en M0 :

```bash
ssh -F infra/secrets/ssh_config -N -L 8000:127.0.0.1:8000 sas-plateforme
```

puis <http://localhost:8000> dans le navigateur.

### 4. La démo

1. Se connecter (`admin`, le mot de passe choisi). Les autres comptes se créent dans « Comptes ».
2. « Demander un paquet » : `pypi`, `requests`. Le catalogue montre `requests` et ses dépendances
   (`urllib3`, `idna`, `certifi`, `charset-normalizer`) `en_attente`.
3. Attendre un tour de `traiter()` : chacune passe `en_analyse`, `approuvee`, puis `publiee`. Une
   version qui reste `approuvee` a vu sa copie échouer : la raison est sur sa fiche, et elle est
   retentée au tour suivant.
4. Preuve sur le serveur : `infra/aws/verifier_h3.sh` (routes, `curl` qui échoue, `pip install
   requests` qui marche, `flask` introuvable).
5. `infra/aws/detruire.sh` après la séance.

Les versions choisies sont publiées depuis plus de 3 jours : le délai ne gêne pas cette démo.
