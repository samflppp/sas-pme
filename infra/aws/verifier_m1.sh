#!/usr/bin/env bash
# Clôture du M1 côté C — les 3 constats qui ne peuvent se faire que sur une infra AWS vivante :
#   1. Inventaire : le serveur installe un paquet via la passerelle, puis /v1/inventory (TLS mutuel,
#      depuis la plateforme) le liste — paquet, version, téléchargements, machine.
#   2. Durcissement ufw : un port non prévu est refusé, et verifier_h3.sh donne toujours 5 OK.
#   3. Tests marqués : pytest -m "docker or ollama" sur la plateforme.
# À lancer depuis votre poste, APRÈS creer.sh puis installer.sh. Sortie à coller dans le point C.
set -uo pipefail
cd "$(dirname "$0")"
source ./config.env; source ./etat.env
export AWS_DEFAULT_REGION="$REGION"
SSH="ssh -F ../secrets/ssh_config"
ok() { echo "  OK  $*"; }; ko() { echo "  KO  $*"; ECHEC=1; }; ECHEC=0

echo "=============================================================="
echo " Clôture M1 (C) — inventaire, durcissement ufw, tests marqués"
echo "=============================================================="

echo
echo "1. Inventaire : pip install depuis le serveur, puis /v1/inventory depuis la plateforme"
# a) le serveur installe un paquet déjà publié via la passerelle (comme verifier_h3.sh §4)
if $SSH sas-serveur '~/app/bin/pip install -q --no-cache-dir --force-reinstall requests' >/dev/null 2>&1; then
  ok "serveur : pip install requests via la passerelle"
else
  ko "serveur : pip install requests a échoué (requests est-il publié ?)"
fi
# b) la plateforme interroge /v1/inventory en TLS mutuel ; on vérifie que requests y figure
INV=$($SSH sas-plateforme 'cd ~/sas/tls && curl -fsS \
      --cacert ca.pem --cert plateforme.pem --key plateforme.key \
      https://10.42.2.10:8443/v1/inventory' 2>/dev/null)
echo "    réponse brute /v1/inventory :"
echo "$INV" | sed 's/^/      /'
if echo "$INV" | grep -q '"nom": *"requests"'; then
  ok "/v1/inventory liste requests (lu dans le journal de pypiserver)"
else
  ko "/v1/inventory ne liste pas requests (journal écrit ? SAS_JOURNAL_ACCES ?)"
fi
# c) le champ machine (hors contrat, option b) expose l'IP du serveur
if echo "$INV" | grep -q '10.42.2.20'; then
  ok "machine 10.42.2.20 (serveur) présente dans le JSON brut"
else
  echo "  --  machine du serveur non vue (vérifier --log-req-frmt REMOTE_ADDR)"
fi

echo
echo "2. Durcissement ufw : un port non prévu est refusé"
# ufw doit bloquer tout sauf 22/8443 depuis la plateforme et 8080/4873 depuis le serveur.
# Depuis la plateforme, un port non autorisé (ex. 9999) doit tomber en timeout (DROP).
if $SSH sas-plateforme 'nc -z -w 5 10.42.2.10 9999' >/dev/null 2>&1; then
  ko "port 9999 de la passerelle JOIGNABLE depuis la plateforme (ufw ne bloque pas)"
else
  ok "port 9999 de la passerelle refusé depuis la plateforme (ufw DROP)"
fi
# Le serveur ne doit PAS joindre le récepteur (8443 réservé à la plateforme)
if $SSH sas-serveur 'nc -z -w 5 10.42.2.10 8443' >/dev/null 2>&1; then
  ko "le serveur joint le port 8443 (récepteur) — ufw devrait le réserver à la plateforme"
else
  ok "le serveur ne joint pas 8443 (réservé à la plateforme)"
fi
# Et le port légitime (8080 pypiserver depuis le serveur) doit, lui, répondre
if $SSH sas-serveur 'curl -fsS -m 8 -o /dev/null http://10.42.2.10:8080/simple/' >/dev/null 2>&1; then
  ok "le serveur joint 8080 (pypiserver) — règle légitime préservée"
else
  ko "le serveur ne joint plus 8080 (ufw trop restrictif ?)"
fi
# ufw statut, pour la trace dans le point
echo "    ufw status (passerelle) :"
$SSH sas-passerelle 'sudo ufw status verbose' 2>/dev/null | sed 's/^/      /'

echo
echo "3. verifier_h3.sh doit toujours donner 5 OK sur 5"
if bash ./verifier_h3.sh; then
  ok "verifier_h3.sh : 5 OK sur 5 (cloisonnement intact après durcissement)"
else
  ko "verifier_h3.sh a signalé un échec (voir ci-dessus)"
fi

echo
echo "4. Tests marqués docker/ollama sur la plateforme"
# La plateforme a Docker (sandbox) et Ollama (LLM) ; on y lance la suite marquée. Le dépôt n'y est
# pas forcément présent (l'installer n'envoie le code qu'à la passerelle), alors on y pousse une
# archive de HEAD, on l'extrait et on lance pytest dedans. (Nécessite git ici et sur la plateforme.)
( cd ../.. && git archive --format=tar.gz HEAD ) \
  | $SSH sas-plateforme 'rm -rf ~/sas-code && mkdir ~/sas-code && tar xzf - -C ~/sas-code' 2>/dev/null
$SSH sas-plateforme bash -s <<'EOF' | sed 's/^/      /'
set -uo pipefail
cd ~/sas-code || { echo "dépôt absent sur la plateforme"; exit 2; }
python3 -m venv .venv && . .venv/bin/activate
pip install -q -e ".[dev]" >/dev/null 2>&1
python -m pytest -q -m "docker or ollama"
EOF
if [[ ${PIPESTATUS[0]:-1} -eq 0 ]]; then
  ok "pytest -m 'docker or ollama' : vert sur la plateforme"
else
  ko "pytest -m 'docker or ollama' : échec ou dépôt absent (voir ci-dessus)"
fi

echo
echo "=============================================================="
if [[ $ECHEC -eq 0 ]]; then
  echo " M1 côté C : TOUS LES CONSTATS PASSENT — le M1 peut être clos."
else
  echo " M1 côté C : au moins un constat a échoué (voir les KO ci-dessus)."
fi
echo "=============================================================="
exit $ECHEC
