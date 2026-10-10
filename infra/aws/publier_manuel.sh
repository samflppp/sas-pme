#!/usr/bin/env bash
# Test de fumée de l'infra, SANS le pipeline (ni délai, ni analyse) : à n'utiliser que pour vérifier
# le réseau avant que A et B soient branchés. Usage : publier_manuel.sh requests
set -euo pipefail
cd "$(dirname "$0")"
[[ $# -eq 1 && $1 =~ ^[A-Za-z0-9._-]+$ ]] || { echo "usage : $0 <paquet>"; exit 2; }
ssh -F ../secrets/ssh_config sas-plateforme bash -s -- "$1" <<'EOF'
set -euo pipefail
d=$(mktemp -d)
pip3 download -q --only-binary=:all: -d "$d" "$1"      # le paquet ET ses dépendances
scp -q -i ~/.ssh/sas_passerelle "$d"/* ubuntu@10.42.2.10:/srv/pypi/packages/
ls "$d" && rm -rf "$d"
EOF
