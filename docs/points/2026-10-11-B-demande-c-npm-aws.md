# Point B (Mouabd19) — demande à C : activer npm sur la démo AWS — 2026-10-11

Constat de Mouabd19 : sur le site de la démo, npm n'est pas utilisable. Le code de `main` le
propose bien : la page « Demandes » contient `pypi` et `npm` (vérifié en local). En revanche, la
plateforme AWS tourne avec une copie du code antérieure à npm (PR #97 et #99). Son pipeline ne
connaît pas npm, et la passerelle n'a pas Verdaccio.

## Demande à C (STEUSSO), dans l'ordre

1. **Plateforme : code à jour, puis web relancé.**
   ```bash
   ssh -F infra/secrets/ssh_config sas-plateforme
   cd ~/sas-pme && git pull origin main      # ou une copie du dépôt à jour, comme d'habitude
   # arrêter l'uvicorn en cours, puis le relancer avec les mêmes variables (demo/script.md)
   .venv/bin/uvicorn plateforme.web.app:app --host 127.0.0.1 --port 8000
   ```
2. **Plateforme : image de la sandbox npm**, construite d'avance. Sinon, la première analyse npm la
   construit et prend plusieurs minutes.
   ```bash
   docker build -t sas-sandbox-node:2 -f plateforme/sandbox/Dockerfile.node plateforme/sandbox
   ```
3. **Passerelle et serveur : npm hors ligne**, depuis ton poste :
   ```bash
   infra/aws/installer_npm.sh
   ```
   - Il installe Verdaccio sans source amont sur la passerelle, et Node et npm sur le serveur,
     pointés sur la passerelle.
   - Il réinstalle aussi `recepteur.service`. Son adresse d'écoute est maintenant
     `SAS_RECEPTEUR_HOTE`, même défaut `10.42.2.10`, donc rien ne change en réseau local.
   - Attendu à l'étape 5 : trois « OK » (Verdaccio joint, `left-pad` invisible,
     `registry.npmjs.org` injoignable).

## Vérification attendue
- Page « Demandes » : choisir `npm`, demander `demo-npm-sain`, ou un vrai petit paquet comme
  `ms`. La version attend son délai, puis elle est analysée, signée et publiée.
- Sur le serveur : `npm install <paquet>` marche et `curl https://registry.npmjs.org` échoue.
- Limite connue : le panneau « Serveur » (agent d'installation) reste pip seulement. L'étape
  `npm install` se fait à la main sur le serveur.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Étapes 1 à 3 ci-dessus, puis coller la sortie de l'étape 5 de `installer_npm.sh` | npm sur la démo AWS | la sortie |
| C (STEUSSO) | Dire si une demande npm depuis le site va jusqu'à « publiée » | npm sur la démo AWS | oui / l'erreur |
