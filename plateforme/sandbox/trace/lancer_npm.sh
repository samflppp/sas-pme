#!/bin/sh
# Scénario npm de la sandbox, dans le conteneur cible (pendant de lancer.sh pour pip) :
# poser les leurres, déposer le paquet dans node_modules, lancer ses scripts d'installation
# (`npm rebuild` : preinstall, install, postinstall) sans réseau, l'importer, attendre un battement.
# Comme `pip --no-deps`, les dépendances ne sont pas installées : chacune passe sa propre analyse.
set -u
read -r JETON
exec < /dev/null
printf '{"e": "debut", "v": "%s"}\n' "$JETON" >> /journal/trace.jsonl
H="$HOME"
mkdir -p "$H/.aws" "$H/.ssh"
printf '[default]\naws_access_key_id = AKIA%s\naws_secret_access_key = %s\n' "$L_ID" "$L_AWS" > "$H/.aws/credentials"
printf -- '-----BEGIN OPENSSH PRIVATE KEY-----\n%s\n-----END OPENSSH PRIVATE KEY-----\n' "$L_SSH" > "$H/.ssh/id_rsa"
printf '//registry.npmjs.org/:_authToken=%s\n' "$L_NPMRC" > "$H/.npmrc"
printf '[pypi]\nusername = __token__\npassword = pypi-%s\n' "$L_PYPIRC" > "$H/.pypirc"
printf 'https://bot:%s@github.com\n' "$L_GIT" > "$H/.git-credentials"
unset L_ID L_AWS L_SSH L_NPMRC L_PYPIRC L_GIT

# Le paquet est déposé tel quel (l'archive npm a un dossier racine, souvent « package/ »).
APP=/tmp/app
mkdir -p "$APP/node_modules/$SAS_MODULE"
tar xzf "/entree/$SAS_ARCHIVE" --strip-components=1 -C "$APP/node_modules/$SAS_MODULE"
echo '{"name": "sas-sandbox", "private": true}' > "$APP/package.json"
cd "$APP"
# npm lit sa configuration dans ~/.npmrc à chaque commande : on lui en donne une vide hors du HOME,
# pour que seule une lecture du leurre par le paquet soit vue.
: > /tmp/npmrc-sandbox
export npm_config_userconfig=/tmp/npmrc-sandbox npm_config_cache=/tmp/npm-cache \
  npm_config_update_notifier=false
ST="strace -f -qq -s 256 -e trace=openat,execve,connect"
$ST -o /journal/strace_installation.txt \
  npm rebuild --foreground-scripts --offline --no-audit --no-fund "$SAS_MODULE" \
  > /journal/installation.log 2>&1
echo $? > /journal/code_installation

# L'import tourne en arrière-plan et écrit lui-même son code de sortie ; puis le battement.
( $ST -o /journal/strace_import.txt node -e '
    import(process.argv[1]).then(() => 0, (e) => { console.error(String(e)); return 1; })
      .then((c) => { require("fs").writeFileSync("/journal/code_import", String(c)); });
  ' "$SAS_MODULE" > /journal/import.log 2>&1 ) &
debut=$(date +%s)
while [ ! -f /journal/code_import ] && [ $(( $(date +%s) - debut )) -lt 100 ]; do sleep 0.2; done
sleep "$SAS_ATTENTE"
printf '{"e": "fin", "v": "%s"}\n' "$JETON" >> /journal/trace.jsonl
for f in /journal/strace_installation.txt /journal/strace_import.txt; do
  printf 'SAS-FIN %s\n' "$JETON" >> "$f"
done
