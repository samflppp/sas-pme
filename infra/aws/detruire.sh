#!/usr/bin/env bash
# Détruit tout ce que creer.sh a créé (lit etat.env). La plateforme coûte cher : à lancer après chaque séance.
set -uo pipefail
cd "$(dirname "$0")"
source ./config.env
source ./etat.env
export AWS_DEFAULT_REGION="$REGION"

aws ec2 terminate-instances --instance-ids "$I_PLAT" "$I_PASS" "$I_SERV" >/dev/null
aws ec2 wait instance-terminated --instance-ids "$I_PLAT" "$I_PASS" "$I_SERV"
aws ec2 delete-key-pair --key-name "$NOM_CLE"
for sg in "$SG_SERV" "$SG_PASS" "$SG_PLAT"; do   # règles croisées : les vider avant de supprimer
  aws ec2 revoke-security-group-ingress --group-id "$sg" --ip-permissions \
    "$(aws ec2 describe-security-groups --group-ids "$sg" --query 'SecurityGroups[0].IpPermissions')" >/dev/null 2>&1
  aws ec2 revoke-security-group-egress --group-id "$sg" --ip-permissions \
    "$(aws ec2 describe-security-groups --group-ids "$sg" --query 'SecurityGroups[0].IpPermissionsEgress')" >/dev/null 2>&1
done
for sg in "$SG_SERV" "$SG_PASS" "$SG_PLAT"; do aws ec2 delete-security-group --group-id "$sg"; done
aws ec2 delete-subnet --subnet-id "$SUB_PUB"
aws ec2 delete-subnet --subnet-id "$SUB_PRIV"
aws ec2 delete-route-table --route-table-id "$RT_PUB"
aws ec2 delete-route-table --route-table-id "$RT_PRIV"
aws ec2 detach-internet-gateway --internet-gateway-id "$IGW" --vpc-id "$VPC"
aws ec2 delete-internet-gateway --internet-gateway-id "$IGW"
aws ec2 delete-vpc --vpc-id "$VPC"
rm -f etat.env ../secrets/"$NOM_CLE".pem ../secrets/ssh_config ../secrets/known_hosts
echo "Détruit."
