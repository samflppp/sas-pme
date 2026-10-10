#!/usr/bin/env bash
# Installe pypiserver et le récepteur signé sur la passerelle, pip sur le serveur, SANS Internet
# côté privé : la plateforme télécharge les wheels, les copie, et la passerelle installe hors ligne.
# À lancer depuis votre poste, après creer.sh. Les certificats viennent de certificats.sh (hors Git) ;
# la clé de signature est créée SUR la plateforme et n'en sort jamais.
set -euo pipefail
cd "$(dirname "$0")"
SSH="ssh -F ../secrets/ssh_config"
SCP="scp -F ../secrets/ssh_config"

echo "== 1. Plateforme : outils, wheels pour la passerelle, clé SSH du stub publier()"
$SSH sas-plateforme bash -s <<'EOF'
set -euo pipefail
sudo apt-get update -q && sudo DEBIAN_FRONTEND=noninteractive apt-get install -yq python3-pip python3-venv docker.io
sudo usermod -aG docker ubuntu           # sandbox : l'appli lance ses conteneurs (nouvelle session SSH)
rm -rf ~/wheels && mkdir -p ~/wheels
pip3 download -q --only-binary=:all: -d ~/wheels pip pypiserver \
  fastapi uvicorn python-multipart cryptography pydantic
[[ -f ~/.ssh/sas_passerelle ]] || ssh-keygen -q -t ed25519 -N "" -C plateforme-publier -f ~/.ssh/sas_passerelle
EOF
PUB=$($SSH sas-plateforme cat .ssh/sas_passerelle.pub)
PIPWHL=$($SSH sas-plateforme 'basename ~/wheels/pip-*.whl')

echo "== 2. Passerelle : autoriser la clé de la plateforme"
$SSH sas-passerelle "grep -qxF '$PUB' ~/.ssh/authorized_keys || echo '$PUB' >> ~/.ssh/authorized_keys; mkdir -p /tmp/wheels"

echo "== 3. Plateforme → passerelle : copie des wheels"
$SSH sas-plateforme 'scp -q -i ~/.ssh/sas_passerelle -o StrictHostKeyChecking=accept-new ~/wheels/*.whl ubuntu@10.42.2.10:/tmp/wheels/'
$SCP -q ../passerelle/pypiserver.service sas-passerelle:/tmp/

echo "== 4. Passerelle : pypiserver hors ligne"
$SSH sas-passerelle sudo bash -s <<'EOF'
set -euo pipefail
id pypi >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin pypi
mkdir -p /srv/pypi/packages
# Répertoire d'état partagé passerelle : journal d'accès (écrit par pypi) et nonces (écrits par le
# récepteur, membre du groupe pypi). 2770 = setgid (héritage du groupe pypi) + group-write.
install -d -o pypi -g pypi -m 2770 /var/lib/sas
PIP=$(ls /tmp/wheels/pip-*.whl)
rm -rf /opt/pypiserver
python3 "$PIP/pip" install -q --no-index --find-links /tmp/wheels --target /opt/pypiserver pypiserver
cp "$PIP" /srv/pypi/packages/            # pip lui-même, pour amorcer les serveurs
chown -R ubuntu:pypi /srv/pypi/packages  # ubuntu = compte qui reçoit les scp de la plateforme
chmod 755 /srv/pypi/packages
install -m 644 /tmp/pypiserver.service /etc/systemd/system/pypiserver.service
systemctl daemon-reload && systemctl enable --now pypiserver && systemctl restart pypiserver
sleep 2 && curl -fsS -o /dev/null http://127.0.0.1:8080/simple/ && echo "pypiserver OK"
EOF

echo "== 5. Serveur : pip pointé sur la passerelle"
$SSH sas-serveur bash -s -- "$PIPWHL" <<'EOF'
set -euo pipefail
PIPWHL=$1
grep -q ' passerelle$' /etc/hosts || echo '10.42.2.10 passerelle' | sudo tee -a /etc/hosts >/dev/null
printf '[global]\nindex-url = http://passerelle:8080/simple/\ntrusted-host = passerelle\n' | sudo tee /etc/pip.conf >/dev/null
rm -rf ~/app && python3 -m venv --without-pip ~/app
curl -fsS -o "/tmp/$PIPWHL" "http://passerelle:8080/packages/$PIPWHL"
~/app/bin/python "/tmp/$PIPWHL/pip" install -q pip
echo "pip OK : $(~/app/bin/pip --version)"
EOF

echo "== 6. Certificats du lien et clé de signature (créée sur la plateforme)"
bash certificats.sh >/dev/null
T=../secrets/tls
$SSH sas-plateforme bash -s <<'EOF'
set -euo pipefail
umask 077 && mkdir -p ~/sas/tls
[[ -f ~/sas/signature.pem ]] || openssl genpkey -algorithm ed25519 -out ~/sas/signature.pem
EOF
$SCP -q $T/ca.pem $T/plateforme.pem $T/plateforme.key sas-plateforme:sas/tls/
$SSH sas-plateforme 'openssl pkey -in ~/sas/signature.pem -pubout' > $T/plateforme_signature.pub
$SCP -q $T/ca.pem $T/passerelle.pem $T/passerelle.key $T/plateforme_signature.pub \
  ../passerelle/recepteur.service sas-passerelle:/tmp/
( cd ../.. && git archive --format=tar.gz HEAD commun passerelle ) | $SSH sas-passerelle 'cat > /tmp/sas-code.tar.gz'

echo "== 7. Passerelle : récepteur hors ligne (:8443, TLS mutuel)"
$SSH sas-passerelle sudo bash -s <<'EOF'
set -euo pipefail
id recepteur >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin -G pypi recepteur
rm -rf /opt/recepteur && mkdir -p /opt/recepteur/code /etc/sas
tar xzf /tmp/sas-code.tar.gz -C /opt/recepteur/code
PIP=$(ls /tmp/wheels/pip-*.whl)
python3 "$PIP/pip" install -q --no-index --find-links /tmp/wheels --target /opt/recepteur/lib \
  fastapi uvicorn python-multipart cryptography pydantic
install -m 644 /tmp/ca.pem /tmp/passerelle.pem /tmp/plateforme_signature.pub /etc/sas/
install -m 640 -g recepteur /tmp/passerelle.key /etc/sas/
rm -f /tmp/passerelle.key
chmod 2775 /srv/pypi/packages            # groupe pypi : le récepteur y écrit
install -m 644 /tmp/recepteur.service /etc/systemd/system/recepteur.service
systemctl daemon-reload && systemctl enable --now recepteur && systemctl restart recepteur
sleep 3 && systemctl is-active --quiet recepteur && echo "récepteur actif"
EOF

echo "== 8. Passerelle : pare-feu ufw (n'ouvrir que ce qui sert)"
# Règles : 8443 depuis la plateforme (récepteur TLS mutuel) ; 8080 (+ 4873 si npm) depuis le
# serveur (pip/npm) ; SSH depuis la plateforme (bastion) seulement. Tout le reste refusé.
# Les groupes de sécurité AWS font déjà ce filtrage ; ufw est la défense en profondeur sur l'hôte,
# et vaut aussi hors AWS (LAN, WireGuard). Les services tournent déjà sous des comptes sans droits
# (pypi, recepteur : --system, nologin ; voir étapes 4 et 7).
$SSH sas-passerelle sudo bash -s <<'EOF'
set -euo pipefail
command -v ufw >/dev/null || DEBIAN_FRONTEND=noninteractive apt-get install -yq ufw
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow from 10.42.1.10 to any port 22   proto tcp   # SSH : plateforme (bastion) seulement
ufw allow from 10.42.1.10 to any port 8443 proto tcp   # récepteur : plateforme seulement
ufw allow from 10.42.2.20 to any port 8080 proto tcp   # pypiserver : serveur seulement
ufw allow from 10.42.2.20 to any port 4873 proto tcp   # verdaccio (npm, si prévu) : serveur
ufw --force enable
ufw status verbose
EOF

echo "== 9. Plateforme → passerelle : santé en TLS mutuel"
$SSH sas-plateforme bash -s <<'EOF'
cd ~/sas/tls
curl -fsS --cacert ca.pem --cert plateforme.pem --key plateforme.key https://10.42.2.10:8443/v1/health \
  && echo "  ← récepteur OK"
if curl -s -o /dev/null --cacert ca.pem https://10.42.2.10:8443/v1/health; then
  echo "ERREUR : récepteur joignable SANS certificat client"; exit 1
else
  echo "sans certificat client : refusé (attendu)"
fi
EOF

echo "== 10. Plateforme : Ollama (local, 127.0.0.1:11434) et les modèles du LLM"
$SSH sas-plateforme bash -s <<'EOF'
set -euo pipefail
command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh >/dev/null
for i in $(seq 1 30); do curl -fsS -o /dev/null http://127.0.0.1:11434/api/tags && break; sleep 1; done
for m in qwen2.5-coder:7b qwen2.5-coder:3b nomic-embed-text; do ollama pull "$m" >/dev/null && echo "  $m OK"; done
EOF

echo
echo "Fini. Variables pour l'appli sur la plateforme (publication signée, M1) :"
echo "  export SAS_PASSERELLE_URL=https://10.42.2.10:8443 SAS_CLE_SIGNATURE=~/sas/signature.pem"
echo "  export SAS_TLS_CA=~/sas/tls/ca.pem SAS_TLS_CERT=~/sas/tls/plateforme.pem SAS_TLS_CLE=~/sas/tls/plateforme.key"
echo "Stub M0 (scp), si besoin : SAS_PASSERELLE_SSH=ubuntu@10.42.2.10 SAS_PASSERELLE_CLE=~/.ssh/sas_passerelle"
