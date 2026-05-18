#!/bin/sh
set -e

CERT="${CERT_PATH:-/app/certs/client_cert.pem}"
KEY="${KEY_PATH:-/app/certs/client_key.pem}"

if [ ! -f "$CERT" ] || [ ! -f "$KEY" ]; then
    echo "No OPC UA client certificate found, generating..."
    cd /app/ingestors && uv run python /app/utils/certgen/src/main.py
else
    echo "OPC UA client certificate found."
fi

echo "Starting ingestor..."
cd /app/ingestors && exec uv run python src/main.py
