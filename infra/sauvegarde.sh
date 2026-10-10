#!/usr/bin/env bash
# Sauvegarde locale chiffrée de la plateforme (docs/sauvegardes.md, M2) : restic.
#
#   bash infra/sauvegarde.sh sauver      # instantané cohérent de la base + dossiers de configuration
#   bash infra/sauvegarde.sh restaurer   # remet la base et les dossiers depuis le dernier instantané
#   bash infra/sauvegarde.sh verifier    # la chaîne du journal de la base est-elle intacte ?
#
# Variables (aucune valeur secrète dans Git) :
#   RESTIC_REPOSITORY        dépôt restic : disque ou NAS de la PME (ex. /mnt/nas/sas-restic)
#   RESTIC_PASSWORD_FILE     mot de passe du dépôt, fichier 0600 hors de Git ; le dépôt est chiffré
#   SAS_DB                   la base de la plateforme (défaut ~/sas.db)
#   SAS_SAUVEGARDE_DOSSIERS  dossiers de configuration, séparés par « : » (listes fermées, certificats)
#   SAS_CLE_JOURNAL          clé HMAC du journal, pour « verifier » seulement
#   SAS_PYTHON               interpréteur qui voit le paquet du dépôt (défaut python3)
#
# N'entrent jamais dans la sauvegarde : la clé privée de signature, les clés privées (TLS, SSH) et
# la clé HMAC du journal. Elles ont leurs copies hors ligne (docs/sauvegardes.md) ; une sauvegarde
# volée ne permet ni de publier ni de réécrire le journal.
set -euo pipefail

ICI=$(cd "$(dirname "$0")/.." && pwd)
SAS_DB=${SAS_DB:-$HOME/sas.db}
PY=${SAS_PYTHON:-python3}
EXCLURE=(--exclude 'signature*.pem' --exclude '*.key' --exclude 'id_rsa*' --exclude 'id_ed25519*'
         --exclude '.sas-cle-journal' --exclude '*.db' --exclude '*.db-wal' --exclude '*.db-shm')

: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY manquant (dépôt restic local)}"
[ -n "${RESTIC_PASSWORD_FILE:-}" ] && [ -r "$RESTIC_PASSWORD_FILE" ] || {
  echo "RESTIC_PASSWORD_FILE manquant ou illisible : le dépôt doit être chiffré" >&2; exit 2; }
export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE

dossiers() { local IFS=:; for d in ${SAS_SAUVEGARDE_DOSSIERS:-}; do [ -d "$d" ] && echo "$d"; done; }

sauver() {
  restic cat config >/dev/null 2>&1 || restic init >/dev/null
  # Instantané cohérent même en WAL, base ouverte : API de sauvegarde de SQLite, pas une copie.
  local tmp; tmp=$(mktemp -d); trap 'rm -rf "$tmp"' RETURN
  "$PY" -I -c 'import sqlite3, sys
s = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True); d = sqlite3.connect(sys.argv[2])
s.backup(d); d.close(); s.close()' "$SAS_DB" "$tmp/sas.db"
  restic backup --quiet --tag base --stdin --stdin-filename sas.db < "$tmp/sas.db"
  mapfile -t ds < <(dossiers)
  [ ${#ds[@]} -eq 0 ] || restic backup --quiet --tag config "${EXCLURE[@]}" "${ds[@]}"
  restic forget --quiet --keep-daily 30 --prune >/dev/null    # rétention de 30 jours
  echo "sauvegarde faite : $(restic snapshots --compact | tail -n +3 | head -n -2 | wc -l) instantanés"
}

restaurer() {
  local tmp; tmp=$(mktemp -d); trap 'rm -rf "$tmp"' RETURN
  restic dump --tag base latest sas.db > "$tmp/sas.db"
  rm -f "$SAS_DB-wal" "$SAS_DB-shm"
  install -m 0600 "$tmp/sas.db" "$SAS_DB"
  if restic snapshots --tag config --json | grep -q '"id"'; then
    restic restore --quiet --tag config latest --target "$tmp/config"
    while read -r d; do
      [ -d "$tmp/config$d" ] && mkdir -p "$d" && cp -a "$tmp/config$d/." "$d/"
    done < <(local IFS=:; for d in ${SAS_SAUVEGARDE_DOSSIERS:-}; do echo "$d"; done)
  fi
  echo "base restaurée dans $SAS_DB"
}

verifier() {
  PYTHONPATH="$ICI" "$PY" -c 'import sys
from plateforme.db.acces import Base
b = Base(sys.argv[1]); ok, seq = b.verifier_journal()
print(f"journal intact : {b.compter_journal()} entrées" if ok else f"journal ALTÉRÉ à l entrée {seq}")
sys.exit(0 if ok else 1)' "$SAS_DB"
}

case "${1:-}" in
  sauver|restaurer|verifier) "$1" ;;
  *) echo "usage : $0 sauver|restaurer|verifier" >&2; exit 2 ;;
esac
