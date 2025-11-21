#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
NAME="${1:-client}"

if [[ ! -f ca.key || ! -f ca.crt ]]; then
  echo "CA not found. Run ./create_ca.sh first." >&2
  exit 1
fi

echo "Generating client key for ${NAME}..."
openssl genrsa -out "${NAME}.key" 2048

echo "Generating CSR..."
openssl req -new -key "${NAME}.key" \
  -subj "/C=CN/ST=Beijing/L=Beijing/O=Local Demo/OU=Client/CN=${NAME}" \
  -out "${NAME}.csr"

echo "Signing client certificate with local CA..."
cat > "${NAME}.ext" <<EOF
extendedKeyUsage=clientAuth
EOF

openssl x509 -req -in "${NAME}.csr" -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out "${NAME}.crt" -days 365 -sha256 -extfile "${NAME}.ext"

echo "Client certificate generated: ${NAME}.crt (key: ${NAME}.key)"
echo "Export to PKCS#12 if you want to import into browsers:"
echo "  openssl pkcs12 -export -inkey ${NAME}.key -in ${NAME}.crt -name ${NAME} -out ${NAME}.p12"
