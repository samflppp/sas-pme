#!/bin/sh
# Scénario de la sandbox, dans le conteneur cible (docs/architecture.md § 5) :
# poser les leurres, installer l'archive sans réseau, importer le module, attendre un battement.
set -u
# Jeton secret de l'analyse, lu sur l'entrée standard : ni variable d'environnement ni fichier, le
# paquet ne peut pas le lire. Il signe les marques de début et de fin des journaux (B, C2).
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

export SAS_TRACE=/journal/trace.jsonl PYTHONPATH=/outils
# v2 : strace voit aussi le code natif (ctypes, extensions C) que le traceur Python ne voit pas.
ST="strace -f -qq -s 256 -e trace=openat,execve,connect"
export SAS_PHASE=installation
$ST -o /journal/strace_installation.txt \
  python -m pip install -q --no-deps --no-index --no-build-isolation --disable-pip-version-check \
  --target /tmp/site "/entree/$SAS_ARCHIVE" > /journal/installation.log 2>&1
echo $? > /journal/code_installation
# L'import tourne en arrière-plan (strace -f suit aussi ce qu'il détache) ; il écrit lui-même son
# code de sortie. On attend sa fin, puis SAS_ATTENTE s pour voir un battement.
export SAS_PHASE=import SAS_CODE_IMPORT=/journal/code_import
$ST -o /journal/strace_import.txt python /outils/importer.py "$SAS_MODULE" > /journal/import.log 2>&1 &
debut=$(date +%s)
while [ ! -f /journal/code_import ] && [ $(( $(date +%s) - debut )) -lt 100 ]; do sleep 0.2; done
sleep "$SAS_ATTENTE"
# Marques de fin, après le battement : un paquet qui a vidé ou réécrit un journal est vu.
printf '{"e": "fin", "v": "%s"}\n' "$JETON" >> /journal/trace.jsonl
for f in /journal/strace_installation.txt /journal/strace_import.txt; do
  printf 'SAS-FIN %s\n' "$JETON" >> "$f"
done
