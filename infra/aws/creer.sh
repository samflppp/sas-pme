#!/usr/bin/env bash
# M0 — Crée le VPC de démo en eu-west-3 :
#   sous-réseau public  10.42.1.0/24 : plateforme (IP publique, bastion SSH)
#   sous-réseau privé   10.42.2.0/24 : passerelle 10.42.2.10 + serveur 10.42.2.20
#                                      SANS NAT, SANS route vers Internet
# Écrit les identifiants dans etat.env et la clé SSH dans ../secrets/ (hors Git).
set -euo pipefail
cd "$(dirname "$0")"
source ./config.env
: "${MON_IP:?MON_IP manquant dans config.env}"
export AWS_DEFAULT_REGION="$REGION"
SECRETS="$(cd .. && pwd)/secrets"
mkdir -p "$SECRETS" && chmod 700 "$SECRETS"
[[ -e etat.env ]] && { echo "etat.env existe déjà : lancer detruire.sh d'abord"; exit 1; }

etat() { echo "$1=$2" >> etat.env; }
tags() { echo "ResourceType=$1,Tags=[{Key=Name,Value=$2},{Key=Projet,Value=sas-pme}]"; }

# --- Réseau ---
VPC=$(aws ec2 create-vpc --cidr-block 10.42.0.0/16 --tag-specifications "$(tags vpc sas-pme)" \
      --query Vpc.VpcId --output text);                                   etat VPC "$VPC"
aws ec2 modify-vpc-attribute --vpc-id "$VPC" --enable-dns-hostnames

SUB_PUB=$(aws ec2 create-subnet --vpc-id "$VPC" --cidr-block 10.42.1.0/24 --availability-zone "$AZ" \
          --tag-specifications "$(tags subnet sas-public)" --query Subnet.SubnetId --output text)
etat SUB_PUB "$SUB_PUB"
SUB_PRIV=$(aws ec2 create-subnet --vpc-id "$VPC" --cidr-block 10.42.2.0/24 --availability-zone "$AZ" \
           --tag-specifications "$(tags subnet sas-prive)" --query Subnet.SubnetId --output text)
etat SUB_PRIV "$SUB_PRIV"
aws ec2 modify-subnet-attribute --subnet-id "$SUB_PUB" --map-public-ip-on-launch

IGW=$(aws ec2 create-internet-gateway --tag-specifications "$(tags internet-gateway sas-igw)" \
      --query InternetGateway.InternetGatewayId --output text);           etat IGW "$IGW"
aws ec2 attach-internet-gateway --internet-gateway-id "$IGW" --vpc-id "$VPC"

RT_PUB=$(aws ec2 create-route-table --vpc-id "$VPC" --tag-specifications "$(tags route-table sas-rt-public)" \
         --query RouteTable.RouteTableId --output text);                  etat RT_PUB "$RT_PUB"
aws ec2 create-route --route-table-id "$RT_PUB" --destination-cidr-block 0.0.0.0/0 --gateway-id "$IGW" >/dev/null
aws ec2 associate-route-table --route-table-id "$RT_PUB" --subnet-id "$SUB_PUB" >/dev/null

# Table privée : uniquement la route « local » du VPC. Aucune 0.0.0.0/0, aucun NAT, aucun endpoint.
RT_PRIV=$(aws ec2 create-route-table --vpc-id "$VPC" --tag-specifications "$(tags route-table sas-rt-prive)" \
          --query RouteTable.RouteTableId --output text);                 etat RT_PRIV "$RT_PRIV"
aws ec2 associate-route-table --route-table-id "$RT_PRIV" --subnet-id "$SUB_PRIV" >/dev/null

# --- Groupes de sécurité ---
sg() { aws ec2 create-security-group --vpc-id "$VPC" --group-name "$1" --description "$2" \
       --tag-specifications "$(tags security-group "$1")" --query GroupId --output text; }
SG_PLAT=$(sg sas-plateforme "plateforme agreee");  etat SG_PLAT "$SG_PLAT"
SG_PASS=$(sg sas-passerelle "passerelle sans Internet"); etat SG_PASS "$SG_PASS"
SG_SERV=$(sg sas-serveur "serveur sensible sans Internet"); etat SG_SERV "$SG_SERV"

entree() {  # entree <sg> <port> <source : CIDR ou sg-…>
  local src; [[ $3 == sg-* ]] && src="UserIdGroupPairs=[{GroupId=$3}]" || src="IpRanges=[{CidrIp=$3}]"
  aws ec2 authorize-security-group-ingress --group-id "$1" \
      --ip-permissions "IpProtocol=tcp,FromPort=$2,ToPort=$2,$src" >/dev/null
}
sortie() {  # sortie <sg> <port> <sg destination>
  aws ec2 authorize-security-group-egress --group-id "$1" \
      --ip-permissions "IpProtocol=tcp,FromPort=$2,ToPort=$2,UserIdGroupPairs=[{GroupId=$3}]" >/dev/null
}
fermer_sortie() {  # retire la règle par défaut « tout sortant »
  aws ec2 revoke-security-group-egress --group-id "$1" \
      --ip-permissions 'IpProtocol=-1,IpRanges=[{CidrIp=0.0.0.0/0}]' >/dev/null
}

# Plateforme : SSH et web depuis votre IP seulement ; sortie libre (elle seule parle à Internet).
entree "$SG_PLAT" 22  "$MON_IP/32"
entree "$SG_PLAT" 443 "$MON_IP/32"
# Passerelle : SSH (stub scp M0) et récepteur 8443 depuis la plateforme ; dépôts depuis le serveur.
entree "$SG_PASS" 22   "$SG_PLAT"
entree "$SG_PASS" 8443 "$SG_PLAT"
for p in 8080 4873 3128; do entree "$SG_PASS" "$p" "$SG_SERV"; done
fermer_sortie "$SG_PASS"
sortie "$SG_PASS" 3129 "$SG_PLAT"          # relais d'API (M2) : passerelle → plateforme seulement
# Serveur : SSH par le bastion seulement ; ne sort que vers la passerelle.
entree "$SG_SERV" 22 "$SG_PLAT"
fermer_sortie "$SG_SERV"
for p in 8080 4873 3128; do sortie "$SG_SERV" "$p" "$SG_PASS"; done

# --- Clé SSH (stockée hors Git) ---
aws ec2 create-key-pair --key-name "$NOM_CLE" --key-type ed25519 \
    --query KeyMaterial --output text > "$SECRETS/$NOM_CLE.pem"
chmod 600 "$SECRETS/$NOM_CLE.pem";                                         etat NOM_CLE "$NOM_CLE"

# --- Instances (Ubuntu 24.04, IMDSv2 obligatoire) ---
AMI=$(aws ssm get-parameter --query Parameter.Value --output text \
      --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id)
instance() {  # instance <nom> <type> <sous-réseau> <sg> <ip privée> <disque Go>
  aws ec2 run-instances --image-id "$AMI" --instance-type "$2" --key-name "$NOM_CLE" \
      --subnet-id "$3" --security-group-ids "$4" --private-ip-address "$5" \
      --metadata-options HttpTokens=required \
      --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=$6,VolumeType=gp3,Encrypted=true}" \
      --tag-specifications "$(tags instance "$1")" --query 'Instances[0].InstanceId' --output text
}
I_PLAT=$(instance sas-plateforme "$TYPE_PLATEFORME" "$SUB_PUB"  "$SG_PLAT" 10.42.1.10 100); etat I_PLAT "$I_PLAT"
I_PASS=$(instance sas-passerelle "$TYPE_PRIVE"      "$SUB_PRIV" "$SG_PASS" 10.42.2.10 20);  etat I_PASS "$I_PASS"
I_SERV=$(instance sas-serveur    "$TYPE_PRIVE"      "$SUB_PRIV" "$SG_SERV" 10.42.2.20 20);  etat I_SERV "$I_SERV"

aws ec2 wait instance-running --instance-ids "$I_PLAT" "$I_PASS" "$I_SERV"
IP_PLAT=$(aws ec2 describe-instances --instance-ids "$I_PLAT" \
          --query 'Reservations[0].Instances[0].PublicIpAddress' --output text); etat IP_PLAT "$IP_PLAT"

# --- Configuration SSH : la plateforme sert de bastion ---
cat > "$SECRETS/ssh_config" <<EOF
Host sas-*
  User ubuntu
  IdentityFile $SECRETS/$NOM_CLE.pem
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
  UserKnownHostsFile $SECRETS/known_hosts
Host sas-plateforme
  HostName $IP_PLAT
Host sas-passerelle
  HostName 10.42.2.10
  ProxyJump sas-plateforme
Host sas-serveur
  HostName 10.42.2.20
  ProxyJump sas-plateforme
EOF
echo "OK. Plateforme : $IP_PLAT — ssh -F infra/secrets/ssh_config sas-serveur"
echo "Ensuite : infra/aws/installer.sh"
