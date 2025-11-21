#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
NAME="${1:-auth-server}"

if [[ ! -f ca.key || ! -f ca.crt ]]; then
  echo "CA not found. Run ./create_ca.sh first." >&2
  exit 1
fi

echo "Generating key for ${NAME}..."
openssl genrsa -out "${NAME}.key" 2048

echo "Generating CSR for ${NAME}..."
openssl req -new -key "${NAME}.key" \
  -subj "/C=CN/ST=Beijing/L=Beijing/O=Local Demo/OU=Server/CN=${NAME}" \
  -out "${NAME}.csr"

echo "Signing certificate with local CA..."
cat > "${NAME}.ext" <<EOF
subjectAltName=DNS:localhost,IP:127.0.0.1
extendedKeyUsage=serverAuth
EOF

openssl x509 -req -in "${NAME}.csr" -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out "${NAME}.crt" -days 365 -sha256 -extfile "${NAME}.ext"

echo "Server certificate generated: ${NAME}.crt (key: ${NAME}.key)"
