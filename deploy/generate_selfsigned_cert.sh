#!/usr/bin/env bash
# Generate a self-signed certificate for local TLS verification.
# Output is gitignored (deploy/certs/*.crt|*.key) — never commit these files.
# Usage:
#   bash deploy/generate_selfsigned_cert.sh
#   docker compose --env-file backend/.env -f docker-compose.yml -f deploy/docker-compose.tls.yml up -d --build
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CERT_DIR="$ROOT/deploy/certs"
mkdir -p "$CERT_DIR"
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout "$CERT_DIR/selfsigned.key" \
  -out "$CERT_DIR/selfsigned.crt" \
  -subj "/CN=localhost/O=Libro.UZ Local TLS/C=UZ"
echo "Wrote $CERT_DIR/selfsigned.crt and selfsigned.key (gitignored — do not commit)"
