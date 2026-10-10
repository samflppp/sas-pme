#!/usr/bin/env bash
# Met la démo sur un domaine (C) : vitrine sur DOMAINE, interface de la plateforme sur demo.DOMAINE,
# en HTTPS (Caddy + Let's Encrypt). À lancer depuis le poste de C, APRÈS avoir créé chez le
# registraire les enregistrements A de DOMAINE et demo.DOMAINE vers l'IP publique de la plateforme.
#
#   DOMAINE=pipelad.tech bash infra/aws/domaine.sh
#
# Ouvre 80 (validation Let's Encrypt) et 443 au public sur la plateforme, et rien d'autre : le web
# de la plateforme reste sur 127.0.0.1:8000, derrière la connexion ; SSH reste réservé à votre IP.
set -euo pipefail
cd "$(dirname "$0")"
source ./config.env; source ./etat.env
export AWS_DEFAULT_REGION="$REGION"
DOMAINE=${DOMAINE:-pipelad.tech}
SSH="ssh -F ../secrets/ssh_config"

echo "== 1. DNS : $DOMAINE et demo.$DOMAINE doivent pointer sur $IP_PLAT"
# Interrogé depuis la plateforme : c'est elle que Let's Encrypt doit trouver, et le poste de C
# peut ne pas joindre de DNS extérieur.
dns() { $SSH sas-plateforme "dig +short +time=3 $1 $2 @1.1.1.1" 2>/dev/null; }
$SSH sas-plateforme 'command -v dig >/dev/null || sudo apt-get install -yq dnsutils >/dev/null'
for n in "$DOMAINE" "www.$DOMAINE" "demo.$DOMAINE"; do
  ip=$(dns A "$n" | tail -1)
  [ "$ip" = "$IP_PLAT" ] || { echo "  $n → « ${ip:-rien} » : pas encore $IP_PLAT (zone DNS, propagation)"; exit 1; }
  [ -z "$(dns AAAA "$n")" ] || { echo "  $n a un AAAA : le retirer (Let's Encrypt essaierait l'IPv6)"; exit 1; }
  echo "  OK  $n → $ip"
done

echo "== 2. Groupe de sécurité de la plateforme : 80 et 443 ouverts au public"
for p in 80 443; do
  aws ec2 authorize-security-group-ingress --group-id "$SG_PLAT" \
      --ip-permissions "IpProtocol=tcp,FromPort=$p,ToPort=$p,IpRanges=[{CidrIp=0.0.0.0/0,Description=domaine-$DOMAINE}]" \
      >/dev/null 2>&1 && echo "  $p ouvert" || echo "  $p déjà ouvert"
done

echo "== 3. Plateforme : Caddy, vitrine, configuration"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
cp -r ../domaine/vitrine "$TMP/vitrine"; cp ../../demo/schema-reseau.svg "$TMP/vitrine/"
sed "s/DOMAINE/$DOMAINE/g" ../domaine/Caddyfile.modele > "$TMP/Caddyfile"
tar czf "$TMP/domaine.tgz" -C "$TMP" vitrine Caddyfile
scp -q -F ../secrets/ssh_config "$TMP/domaine.tgz" sas-plateforme:/tmp/domaine.tgz
$SSH sas-plateforme 'set -e
  command -v caddy >/dev/null || sudo DEBIAN_FRONTEND=noninteractive apt-get install -yq caddy >/dev/null
  rm -rf /tmp/domaine && mkdir /tmp/domaine && tar xzf /tmp/domaine.tgz -C /tmp/domaine
  sudo rm -rf /var/www/vitrine && sudo mkdir -p /var/www && sudo cp -r /tmp/domaine/vitrine /var/www/vitrine
  sudo install -m 0644 /tmp/domaine/Caddyfile /etc/caddy/Caddyfile
  sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
  sudo systemctl enable --now caddy >/dev/null 2>&1; sudo systemctl reload caddy'

echo "== 4. Vérification (le premier certificat peut prendre une minute)"
for i in $(seq 1 12); do
  v=$(curl -s -o /dev/null -w '%{http_code}' -m 10 "https://$DOMAINE/" || true)
  d=$(curl -s -o /dev/null -w '%{http_code}' -m 10 "https://demo.$DOMAINE/connexion" || true)
  [ "$v" = 200 ] && [ "$d" = 200 ] && break; sleep 10
done
echo "  https://$DOMAINE/ → $v ; https://demo.$DOMAINE/connexion → $d"
[ "$v" = 200 ] && [ "$d" = 200 ] || { echo "  voir : $SSH sas-plateforme sudo journalctl -u caddy -n 50"; exit 1; }
curl -s -o /dev/null -w "  http → %{http_code} vers %{redirect_url}\n" "http://$DOMAINE/"
echo "Fini. Le web de la plateforme doit tourner (demo/script.md § 3) pour que demo.$DOMAINE réponde."
