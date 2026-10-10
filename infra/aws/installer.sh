#!/usr/bin/env bash
# M0 — Installe pypiserver sur la passerelle et pip sur le serveur, SANS Internet côté privé :
# la plateforme télécharge les wheels, les copie, et la passerelle installe hors ligne.
# À lancer depuis votre poste, après creer.sh.
set -euo pipefail
cd "$(dirname "$0")"
SSH="ssh -F ../secrets/ssh_config"
SCP="scp -F ../secrets/ssh_config"

echo "== 1. Plateforme : outils, wheels pour la passerelle, clé SSH du stub publier()"
$SSH sas-plateforme bash -s <<'EOF'
set -euo pipefail
sudo apt-get update -q && sudo DEBIAN_FRONTEND=noninteractive apt-get install -yq python3-pip python3-venv
rm -rf ~/wheels && mkdir -p ~/wheels
pip3 download -q --only-binary=:all: -d ~/wheels pip pypiserver
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

echo
echo "Fini. Variables pour l'appli sur la plateforme (stub signature.publier) :"
echo "  export SAS_PASSERELLE_SSH=ubuntu@10.42.2.10"
echo "  export SAS_PASSERELLE_CLE=/home/ubuntu/.ssh/sas_passerelle"
