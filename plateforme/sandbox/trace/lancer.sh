#!/bin/sh
# Scénario de la sandbox, dans le conteneur cible (docs/architecture.md § 5) :
# poser les leurres, installer l'archive sans réseau, importer le module, attendre un battement.
set -u
H="$HOME"
mkdir -p "$H/.aws" "$H/.ssh"
printf '[default]\naws_access_key_id = AKIA%s\naws_secret_access_key = %s\n' "$L_ID" "$L_AWS" > "$H/.aws/credentials"
printf -- '-----BEGIN OPENSSH PRIVATE KEY-----\n%s\n-----END OPENSSH PRIVATE KEY-----\n' "$L_SSH" > "$H/.ssh/id_rsa"
printf '//registry.npmjs.org/:_authToken=%s\n' "$L_NPMRC" > "$H/.npmrc"
printf '[pypi]\nusername = __token__\npassword = pypi-%s\n' "$L_PYPIRC" > "$H/.pypirc"
printf 'https://bot:%s@github.com\n' "$L_GIT" > "$H/.git-credentials"
unset L_ID L_AWS L_SSH L_NPMRC L_PYPIRC L_GIT

export SAS_TRACE=/journal/trace.jsonl PYTHONPATH=/outils
export SAS_PHASE=installation
python -m pip install -q --no-deps --no-index --no-build-isolation --disable-pip-version-check \
  --target /tmp/site "/entree/$SAS_ARCHIVE" > /journal/installation.log 2>&1
echo $? > /journal/code_installation
export SAS_PHASE=import
python /outils/importer.py "$SAS_MODULE" > /journal/import.log 2>&1
echo $? > /journal/code_import
sleep "$SAS_ATTENTE"
