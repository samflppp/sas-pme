#!/usr/bin/env bash
# Point H3 — preuve du cloisonnement :
#   la table de routage privée n'a aucune route vers Internet ;
#   serveur et passerelle ne joignent pas pypi.org ;
#   le serveur installe requests via la passerelle.
set -uo pipefail
cd "$(dirname "$0")"
source ./config.env; source ./etat.env
export AWS_DEFAULT_REGION="$REGION"
SSH="ssh -F ../secrets/ssh_config"
ok() { echo "  OK  $*"; }; ko() { echo "  KO  $*"; ECHEC=1; }; ECHEC=0

echo "1. Routes du sous-réseau privé (attendu : 10.42.0.0/16 seulement)"
ROUTES=$(aws ec2 describe-route-tables --route-table-ids "$RT_PRIV" \
         --query 'RouteTables[0].Routes[].DestinationCidrBlock' --output text)
[[ $ROUTES == "10.42.0.0/16" ]] && ok "$ROUTES" || ko "routes : $ROUTES"

echo "2. Serveur → https://pypi.org (doit échouer)"
$SSH sas-serveur 'curl -sS -m 8 -o /dev/null https://pypi.org' 2>/dev/null \
  && ko "le serveur joint Internet !" || ok "curl échoue"

echo "3. Passerelle → https://pypi.org (doit échouer)"
$SSH sas-passerelle 'curl -sS -m 8 -o /dev/null https://pypi.org' 2>/dev/null \
  && ko "la passerelle joint Internet !" || ok "curl échoue"

echo "4. Serveur : pip install requests via la passerelle"
if $SSH sas-serveur '~/app/bin/pip install -q --no-cache-dir --force-reinstall requests \
                     && ~/app/bin/python -c "import requests; print(requests.__version__)"'; then
  ok "requests installé depuis http://passerelle:8080/simple/"
else
  ko "pip install requests (requests et ses dépendances sont-ils publiés ?)"
fi

echo "5. Serveur : un paquet non publié est introuvable (pas de repli vers pypi.org)"
$SSH sas-serveur '~/app/bin/pip install -q --no-cache-dir flask' >/dev/null 2>&1 \
  && ko "flask installé alors qu'il n'est pas publié" || ok "flask introuvable"

exit $ECHEC
