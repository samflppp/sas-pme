#!/usr/bin/env bash
# npm sur la démo AWS, après installer.sh : Verdaccio sans source amont sur la passerelle, Node et
# npm sur le serveur, pointés sur la passerelle. Comme pour pip, tout est téléchargé par la
# plateforme (seule reliée à Internet), vérifié, puis copié ; la passerelle et le serveur
# installent hors ligne. installer.sh a retiré la clé de la plateforme de la passerelle (B : C3) :
# les fichiers passent donc par le poste de l'opérateur (ssh … | ssh …), jamais en direct.
# À lancer depuis votre poste. Le jeton de publication de Verdaccio est tiré sur la passerelle et
# n'en sort jamais (lu par le seul récepteur, /var/lib/sas-recepteur, 0600).
set -euo pipefail
cd "$(dirname "$0")"
SSH="ssh -F ../secrets/ssh_config"
SCP="scp -F ../secrets/ssh_config"
NODE=v20.19.5                     # Node 20 LTS, comme la sandbox (Dockerfile.node)
VERDACCIO=6.1.6

echo "== 1. Plateforme : Node (somme SHA-256 vérifiée) et Verdaccio, prêts à copier"
$SSH sas-plateforme bash -s -- "$NODE" "$VERDACCIO" <<'EOF'
set -euo pipefail
NODE=$1 VERDACCIO=$2
rm -rf ~/npm-hors-ligne && mkdir -p ~/npm-hors-ligne && cd ~/npm-hors-ligne
F="node-$NODE-linux-x64.tar.xz"
curl -fsSO "https://nodejs.org/dist/$NODE/$F"
curl -fsS "https://nodejs.org/dist/$NODE/SHASUMS256.txt" | grep " $F\$" | sha256sum -c -
mkdir node && tar xJf "$F" --strip-components=1 -C node && rm "$F"
# Verdaccio et ses dépendances, installés ici (scripts d'installation désactivés), copiés tels quels.
mkdir verdaccio && ./node/bin/npm install --prefix verdaccio --omit=dev --ignore-scripts \
  --no-audit --no-fund "verdaccio@$VERDACCIO" >/dev/null
tar czf ../npm-hors-ligne.tar.gz node verdaccio
echo "prêt : $(du -h ../npm-hors-ligne.tar.gz | cut -f1)"
EOF

echo "== 2. Plateforme → poste → passerelle et serveur (aucune clé de la plateforme utilisée)"
$SSH sas-plateforme 'cat ~/npm-hors-ligne.tar.gz' | $SSH sas-passerelle 'cat > /tmp/npm-hors-ligne.tar.gz'
$SSH sas-plateforme 'cat ~/npm-hors-ligne.tar.gz' | $SSH sas-serveur 'cat > /tmp/npm-hors-ligne.tar.gz'
$SCP -q ../passerelle/verdaccio.yaml ../passerelle/verdaccio.service ../passerelle/recepteur.service \
  sas-passerelle:/tmp/

echo "== 3. Passerelle : Verdaccio hors ligne (:4873), compte de publication du seul récepteur"
$SSH sas-passerelle sudo bash -s <<'EOF'
set -euo pipefail
id verdaccio >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin -G pypi verdaccio
rm -rf /opt/node /opt/verdaccio && mkdir -p /tmp/npm && tar xzf /tmp/npm-hors-ligne.tar.gz -C /tmp/npm
mv /tmp/npm/node /opt/node && mv /tmp/npm/verdaccio /opt/verdaccio && rm -rf /tmp/npm
install -d -o verdaccio -g verdaccio -m 700 /var/lib/verdaccio /var/lib/verdaccio/storage
install -d -m 755 /etc/verdaccio
# Le temps de créer le compte « recepteur », une seule inscription est ouverte ; puis plus aucune.
sed 's/max_users: -1/max_users: 1/' /tmp/verdaccio.yaml > /etc/verdaccio/config.yaml
chmod 644 /etc/verdaccio/config.yaml
install -m 644 /tmp/verdaccio.service /etc/systemd/system/verdaccio.service
systemctl daemon-reload && systemctl enable --now verdaccio && systemctl restart verdaccio
for i in $(seq 1 30); do curl -fsS -o /dev/null http://127.0.0.1:4873/-/ping && break; sleep 1; done
if [[ ! -s /var/lib/sas-recepteur/verdaccio.jeton ]]; then
  MDP=$(head -c 32 /dev/urandom | base64 | tr -d '/+=')
  REPONSE=$(curl -fsS -X PUT -H 'content-type: application/json' \
    -d "{\"name\":\"recepteur\",\"password\":\"$MDP\"}" \
    http://127.0.0.1:4873/-/user/org.couchdb.user:recepteur)
  JETON=$(printf '%s' "$REPONSE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
  install -o recepteur -g recepteur -m 600 /dev/null /var/lib/sas-recepteur/verdaccio.jeton
  printf '%s' "$JETON" > /var/lib/sas-recepteur/verdaccio.jeton
  unset MDP REPONSE JETON
fi
install -m 644 /tmp/verdaccio.yaml /etc/verdaccio/config.yaml      # max_users: -1
systemctl restart verdaccio
for i in $(seq 1 30); do curl -fsS -o /dev/null http://127.0.0.1:4873/-/ping && break; sleep 1; done
# Aucune source amont : un paquet jamais publié répond 404.
test "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:4873/left-pad)" = 404 \
  && echo "Verdaccio OK, sans source amont"
# Plus d'inscription possible.
test "$(curl -s -o /dev/null -w '%{http_code}' -X PUT -H 'content-type: application/json' \
  -d '{"name":"intrus","password":"un-mot-de-passe-long"}' \
  http://127.0.0.1:4873/-/user/org.couchdb.user:intrus)" != 201 && echo "inscriptions fermées"
install -m 644 /tmp/recepteur.service /etc/systemd/system/recepteur.service
systemctl daemon-reload && systemctl restart recepteur
sleep 3 && systemctl is-active --quiet recepteur && echo "récepteur actif (npm branché)"
EOF

echo "== 4. Serveur : Node et npm hors ligne, registre = la passerelle"
$SSH sas-serveur sudo bash -s <<'EOF'
set -euo pipefail
rm -rf /opt/node && mkdir -p /tmp/npm && tar xzf /tmp/npm-hors-ligne.tar.gz -C /tmp/npm node
mv /tmp/npm/node /opt/node && rm -rf /tmp/npm /tmp/npm-hors-ligne.tar.gz
ln -sf /opt/node/bin/node /usr/local/bin/node
ln -sf /opt/node/bin/npm /usr/local/bin/npm
ln -sf /opt/node/bin/npx /usr/local/bin/npx
# npm ne connaît que la passerelle ; le relais d'API (HTTPS_PROXY) ne le concerne pas.
mkdir -p /opt/node/etc
printf 'registry=http://passerelle:4873/\nnoproxy=passerelle\naudit=false\nfund=false\nupdate-notifier=false\n' \
  > /opt/node/etc/npmrc
echo "npm OK : $(npm --version), registre $(npm config get registry)"
EOF

echo "== 5. Vérification depuis le serveur"
$SSH sas-serveur bash -s <<'EOF'
set -uo pipefail
curl -fsS -o /dev/null http://passerelle:4873/-/ping && echo "OK  le serveur joint Verdaccio"
if npm view left-pad version >/dev/null 2>&1; then
  echo "ÉCHEC  left-pad visible : Verdaccio a une source amont"
else
  echo "OK  npm ne voit pas left-pad (jamais publié, aucune source amont)"
fi
if curl -s -m 5 -o /dev/null https://registry.npmjs.org --noproxy '*'; then
  echo "ÉCHEC  le serveur joint registry.npmjs.org"
else
  echo "OK  registry.npmjs.org injoignable depuis le serveur"
fi
EOF
echo
echo "Fini. Une version npm approuvée par la plateforme est publiée, signée, dans Verdaccio ;"
echo "sur le serveur : npm install <paquet>."
