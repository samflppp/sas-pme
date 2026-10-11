#!/usr/bin/env bash
# Mode « plateforme hors site » (extension M2) : le lien plateforme ↔ passerelle passe par WireGuard.
# Le TLS mutuel et la signature des manifestes restent ; le tunnel s'y ajoute, il ne les remplace pas.
#
#   plateforme wg0 10.99.0.1, écoute UDP 51820      passerelle wg0 10.99.0.2, appelle la plateforme
#
# - Chaque clé privée est tirée SUR son hôte (openssl X25519, 0600) et n'en sort jamais ; seules les
#   clés publiques passent par votre poste.
# - systemd-networkd porte le tunnel : rien à installer sur la passerelle, qui n'a pas Internet.
# - Le récepteur n'écoute plus que sur 10.99.0.2 et ufw n'ouvre 8443 qu'à 10.99.0.1 par wg0 :
#   le chemin direct 10.42.2.10:8443 est fermé, on le vérifie.
# - AllowedIPs = le seul pair : la passerelle ne gagne aucune route vers Internet.
#
# À lancer depuis votre poste, après installer.sh :
#   infra/aws/installer_wireguard.sh          passe en mode tunnel
#   infra/aws/installer_wireguard.sh local    revient au réseau local (la démo garantie)
# Ensuite, sur la plateforme : SAS_PASSERELLE_URL=https://passerelle:8443 (le certificat de la
# passerelle porte DNS:passerelle ; /etc/hosts de la plateforme pointe passerelle sur le tunnel).
set -euo pipefail
cd "$(dirname "$0")"
SSH="ssh -F ../secrets/ssh_config"
SCP="scp -F ../secrets/ssh_config"

if [[ "${1:-}" == "local" ]]; then
  echo "== Retour au réseau local : tunnel arrêté, récepteur de nouveau sur 10.42.2.10"
  $SSH sas-passerelle sudo bash -s <<'EOF'
set -euo pipefail
rm -f /etc/systemd/system/recepteur.service.d/wireguard.conf \
      /etc/systemd/system/relais-passerelle.service.d/wireguard.conf \
      /etc/systemd/network/90-sas-wg0.netdev /etc/systemd/network/90-sas-wg0.network
ufw delete allow in on wg0 from 10.99.0.1 to any port 8443 proto tcp >/dev/null 2>&1 || true
ufw allow from 10.42.1.10 to any port 8443 proto tcp
networkctl delete wg0 2>/dev/null || true
systemctl daemon-reload && systemctl restart recepteur relais-passerelle
EOF
  $SSH sas-plateforme sudo bash -s <<'EOF'
set -euo pipefail
rm -f /etc/systemd/system/relais-plateforme.service.d/wireguard.conf \
      /etc/systemd/network/90-sas-wg0.netdev /etc/systemd/network/90-sas-wg0.network
sed -i '/ passerelle$/d' /etc/hosts && echo '10.42.2.10 passerelle' >> /etc/hosts
networkctl delete wg0 2>/dev/null || true
systemctl daemon-reload
systemctl cat relais-plateforme >/dev/null 2>&1 && systemctl restart relais-plateforme || true
EOF
  echo "Fait. SAS_PASSERELLE_URL=https://passerelle:8443 marche toujours (passerelle = 10.42.2.10)."
  exit 0
fi

# Sur chaque hôte : tirer la clé privée une fois, la poser pour networkd, imprimer la publique.
CLES='
set -euo pipefail
umask 077
install -d -m 700 /etc/sas-wg
[[ -s /etc/sas-wg/x25519.pem ]] || openssl genpkey -algorithm X25519 -out /etc/sas-wg/x25519.pem
openssl pkey -in /etc/sas-wg/x25519.pem -outform DER | tail -c 32 | base64 > /etc/systemd/network/wg0.key
chown root:systemd-network /etc/systemd/network/wg0.key && chmod 640 /etc/systemd/network/wg0.key
openssl pkey -in /etc/sas-wg/x25519.pem -pubout -outform DER | tail -c 32 | base64
'
echo "== 1. Clés : tirées sur chaque hôte, seules les publiques sortent"
PUB_PLAT=$($SSH sas-plateforme sudo bash -s <<<"$CLES")
PUB_PASS=$($SSH sas-passerelle sudo bash -s <<<"$CLES")
echo "  plateforme $PUB_PLAT"
echo "  passerelle $PUB_PASS"

echo "== 2. Configurations wg0 (systemd-networkd), rendues ici"
T=$(mktemp -d) && trap 'rm -rf "$T"' EXIT
mkdir "$T/plateforme" "$T/passerelle"
python3 -I ../wireguard/rendre.py plateforme "$PUB_PASS" "$T/plateforme"
python3 -I ../wireguard/rendre.py passerelle "$PUB_PLAT" "$T/passerelle"
$SCP -q "$T"/plateforme/90-sas-wg0.* sas-plateforme:/tmp/
$SCP -q "$T"/passerelle/90-sas-wg0.* sas-passerelle:/tmp/

echo "== 3. Groupes de sécurité : UDP 51820, de la passerelle vers la plateforme seulement"
( source ./config.env; source ./etat.env; export AWS_DEFAULT_REGION="$REGION"
  aws ec2 authorize-security-group-ingress --group-id "$SG_PLAT" --ip-permissions \
    "IpProtocol=udp,FromPort=51820,ToPort=51820,UserIdGroupPairs=[{GroupId=$SG_PASS}]" \
    >/dev/null 2>&1 || echo "  (entrée plateforme déjà là)"
  aws ec2 authorize-security-group-egress --group-id "$SG_PASS" --ip-permissions \
    "IpProtocol=udp,FromPort=51820,ToPort=51820,UserIdGroupPairs=[{GroupId=$SG_PLAT}]" \
    >/dev/null 2>&1 || echo "  (sortie passerelle déjà là)" )

echo "== 4. Plateforme : wg0 10.99.0.1, passerelle = 10.99.0.2, relais d'API sur le tunnel"
$SSH sas-plateforme sudo bash -s <<'EOF'
set -euo pipefail
install -m 644 /tmp/90-sas-wg0.netdev /tmp/90-sas-wg0.network /etc/systemd/network/
systemctl enable --now systemd-networkd >/dev/null 2>&1 || true
networkctl reload
for i in $(seq 1 10); do networkctl status wg0 >/dev/null 2>&1 && break; sleep 1; done
sed -i '/ passerelle$/d' /etc/hosts && echo '10.99.0.2 passerelle' >> /etc/hosts
if systemctl cat relais-plateforme >/dev/null 2>&1; then
  install -d /etc/systemd/system/relais-plateforme.service.d
  printf '[Service]\nEnvironment=SAS_RELAIS_ECOUTE=10.99.0.1:3129\nRestartSec=3\n' \
    > /etc/systemd/system/relais-plateforme.service.d/wireguard.conf
  systemctl daemon-reload && systemctl restart relais-plateforme
fi
EOF

echo "== 5. Passerelle : wg0 10.99.0.2, récepteur sur le tunnel seul, ufw"
$SSH sas-passerelle sudo bash -s <<'EOF'
set -euo pipefail
install -m 644 /tmp/90-sas-wg0.netdev /tmp/90-sas-wg0.network /etc/systemd/network/
networkctl reload
for i in $(seq 1 10); do networkctl status wg0 >/dev/null 2>&1 && break; sleep 1; done
install -d /etc/systemd/system/recepteur.service.d /etc/systemd/system/relais-passerelle.service.d
printf '[Service]\nEnvironment=SAS_RECEPTEUR_HOTE=10.99.0.2\nRestartSec=3\n' \
  > /etc/systemd/system/recepteur.service.d/wireguard.conf
printf '[Service]\nEnvironment=SAS_RELAIS_AMONT=10.99.0.1:3129\nRestartSec=3\n' \
  > /etc/systemd/system/relais-passerelle.service.d/wireguard.conf
ufw allow in on wg0 from 10.99.0.1 to any port 8443 proto tcp
ufw delete allow from 10.42.1.10 to any port 8443 proto tcp >/dev/null 2>&1 || true
systemctl daemon-reload && systemctl restart recepteur relais-passerelle
EOF

echo "== 6. Vérification"
sleep 5
$SSH sas-plateforme bash -s <<'EOF'
set -uo pipefail
cd ~/sas/tls
ping -c 2 -W 3 10.99.0.2 >/dev/null && echo "OK  tunnel monté (10.99.0.2 répond)" \
  || echo "ÉCHEC  pas de réponse de 10.99.0.2 par le tunnel"
curl -fsS -m 10 --cacert ca.pem --cert plateforme.pem --key plateforme.key \
  https://passerelle:8443/v1/health >/dev/null \
  && echo "OK  récepteur joint par le tunnel, en TLS mutuel (https://passerelle:8443)" \
  || echo "ÉCHEC  récepteur injoignable par le tunnel"
if curl -s -m 8 -o /dev/null --cacert ca.pem --cert plateforme.pem --key plateforme.key \
     --resolve passerelle:8443:10.42.2.10 https://passerelle:8443/v1/health; then
  echo "ÉCHEC  https://10.42.2.10:8443 joignable hors du tunnel"
else
  echo "OK  https://10.42.2.10:8443 refusé : le récepteur n'est joignable que par le tunnel"
fi
EOF
$SSH sas-passerelle bash -s <<'EOF'
set -uo pipefail
if ip route get 1.1.1.1 2>/dev/null | grep -q wg0; then
  echo "ÉCHEC  la passerelle route Internet par le tunnel"
elif curl -s -m 5 -o /dev/null https://1.1.1.1; then
  echo "ÉCHEC  la passerelle joint Internet"
else
  echo "OK  la passerelle reste sans Internet, tunnel monté"
fi
EOF
$SSH sas-serveur bash -s <<'EOF'
set -uo pipefail
code=$(HTTPS_PROXY=http://passerelle:3128 curl -s -o /dev/null -w '%{http_code}' -m 15 \
  https://api.github.com || true)
[[ $code == 200 ]] && echo "OK  relais d'API par le tunnel (api.github.com : 200)" \
  || echo "ÉCHEC  relais d'API : $code"
EOF
echo
echo "Fini. Sur la plateforme : export SAS_PASSERELLE_URL=https://passerelle:8443"
echo "Retour au réseau local : $0 local"
