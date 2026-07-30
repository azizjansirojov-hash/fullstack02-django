#!/usr/bin/env bash
# Generate a self-signed certificate for local TLS verification.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CERT_DIR="$ROOT/deploy/certs"
mkdir -p "$CERT_DIR"
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout "$CERT_DIR/selfsigned.key" \
  -out "$CERT_DIR/selfsigned.crt" \
  -subj "/CN=localhost/O=Libro.UZ Local TLS/C=UZ"
echo "Wrote $CERT_DIR/selfsigned.crt and selfsigned.key"
