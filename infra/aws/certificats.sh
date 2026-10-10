#!/usr/bin/env bash
# M1 — Certificats du lien plateforme ↔ passerelle (TLS mutuel), dans infra/secrets/tls/ (hors Git).
# Une petite autorité locale signe le certificat serveur de la passerelle et le certificat client de
# la plateforme. La clé de l'autorité ne quitte pas ce poste. Ne recrée rien de ce qui existe.
set -euo pipefail
cd "$(dirname "$0")"
D=../secrets/tls
mkdir -p "$D" && chmod 700 "$D" && cd "$D"
umask 077

[[ -f ca.key ]] || {
  openssl req -x509 -new -nodes -newkey ec -pkeyopt ec_paramgen_curve:P-256 -days 30 \
    -subj "/CN=sas-pme autorite du lien" -keyout ca.key -out ca.pem \
    -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign" \
    -addext "subjectKeyIdentifier=hash" 2>/dev/null
}

certificat() {  # nom, extensions
  [[ -f $1.pem ]] && return
  openssl req -new -nodes -newkey ec -pkeyopt ec_paramgen_curve:P-256 -subj "/CN=$1" \
    -keyout "$1.key" -out "$1.csr" 2>/dev/null
  printf '%s\n' "$2" > "$1.ext"
  openssl x509 -req -in "$1.csr" -CA ca.pem -CAkey ca.key -CAcreateserial -days 30 \
    -extfile "$1.ext" -out "$1.pem" 2>/dev/null
  rm -f "$1.csr" "$1.ext"
}

certificat passerelle "basicConstraints=CA:FALSE
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid
keyUsage=digitalSignature
extendedKeyUsage=serverAuth
subjectAltName=IP:10.42.2.10,DNS:passerelle"
certificat plateforme "basicConstraints=CA:FALSE
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid
keyUsage=digitalSignature
extendedKeyUsage=clientAuth"

openssl verify -CAfile ca.pem passerelle.pem plateforme.pem
