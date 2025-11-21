#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Generating CA key..."
openssl genrsa -out ca.key 4096

echo "Generating CA certificate..."
openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 \
  -subj "/C=CN/ST=Beijing/L=Beijing/O=Local Demo/OU=CA/CN=Local Demo CA" \
  -out ca.crt

echo "Created ca.crt (public) and ca.key (private). Keep ca.key secret."
