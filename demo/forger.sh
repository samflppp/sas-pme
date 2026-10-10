#!/usr/bin/env bash
# Démo H10, étape 3 — « Même la plateforme usurpée ne peut rien publier. »
# À lancer SUR la plateforme, depuis ~/sas-pme. L'attaquant a pris le lien réseau (il a le
# certificat TLS de la plateforme) mais pas la clé de signature : il signe avec sa propre clé une
# fausse version de requests. La passerelle répond 401 et rien n'arrive sur le serveur.
set -euo pipefail
cd "$(dirname "$0")/.."
PAQUET=${1:-requests}
VERSION=${2:-99.0.0}
TMP=$(mktemp -d) && trap 'rm -rf "$TMP"' EXIT

printf 'import os  # charge malveillante de démo, jamais exécutée\n' > "$TMP/x.py"
ROUE="$TMP/${PAQUET//-/_}-$VERSION-py3-none-any.whl"
(cd "$TMP" && python3 -m zipfile -c "$ROUE" x.py)

: "${SAS_TLS_CA:=$HOME/sas/tls/ca.pem}" "${SAS_TLS_CERT:=$HOME/sas/tls/plateforme.pem}"
: "${SAS_TLS_CLE:=$HOME/sas/tls/plateforme.key}" "${SAS_PASSERELLE_URL:=https://10.42.2.10:8443}"
export SAS_TLS_CA SAS_TLS_CERT SAS_TLS_CLE SAS_PASSERELLE_URL
export SAS_CLE_SIGNATURE="$TMP/cle_de_l_attaquant.pem"     # PAS la clé de la plateforme

echo "== Publication forgée de $PAQUET $VERSION, signée avec la clé de l'attaquant"
.venv/bin/python - "$PAQUET" "$VERSION" "$ROUE" <<'EOF'
import sys
from pathlib import Path
from plateforme import signature
from plateforme.signature import ed25519

paquet, version, roue = sys.argv[1:]
ed25519.generer_cle(Path(signature.os.environ["SAS_CLE_SIGNATURE"]))
try:
    signature.publier("pypi", paquet, version, [Path(roue)], verdict_id=0)
except signature.PublicationRefusee as e:
    print(f"REFUSÉE par la passerelle : {e}")
    sys.exit(0)
print("ERREUR : la passerelle a accepté une publication forgée")
sys.exit(1)
EOF
