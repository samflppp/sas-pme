#!/usr/bin/env bash
# Test de fumée de l'infra, SANS le pipeline ni la signature : vérifier le réseau seulement. Geste
# d'administration : il passe par la clé de l'opérateur (pas par la plateforme, qui n'a plus d'accès
# SSH à la passerelle, B : C3) et dépose les archives au nom du récepteur. Usage : publier_manuel.sh requests
set -euo pipefail
cd "$(dirname "$0")"
[[ $# -eq 1 && $1 =~ ^[A-Za-z0-9._-]+$ ]] || { echo "usage : $0 <paquet>"; exit 2; }
SSH="ssh -F ../secrets/ssh_config"
$SSH sas-plateforme "d=\$(mktemp -d) && pip3 download -q --only-binary=:all: -d \$d '$1' >&2 \
  && tar -C \$d -cf - . && rm -rf \$d" \
  | $SSH sas-passerelle 'd=$(mktemp -d) && tar -C "$d" -xf - && sudo install -o recepteur -g pypi -m 644 "$d"/* /srv/pypi/packages/ && ls "$d" && rm -rf "$d"'
