#!/usr/bin/env bash
# Point H3 — preuve du cloisonnement :
#   la table de routage privée n'a aucune route vers Internet ;
#   serveur et passerelle ne joignent pas pypi.org ;
#   le serveur installe requests via la passerelle ;
#   le serveur ne résout aucun nom (pas de fuite par DNS, constat C5 de B).
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

echo "6. Serveur : aucune résolution DNS (sinon un paquet peut faire fuir des données par DNS)"
NOM="sas-verif-$RANDOM.example.net"
$SSH sas-serveur "sudo resolvectl flush-caches 2>/dev/null; timeout 8 getent hosts exemple.com \
  || timeout 8 dig +short +time=2 +tries=1 @10.42.0.2 $NOM | grep -qE '^[0-9a-f.:]+$'" >/dev/null 2>&1 \
  && ko "le serveur résout des noms (DNS du VPC actif ?)" || ok "aucune résolution DNS"

exit $ECHEC
