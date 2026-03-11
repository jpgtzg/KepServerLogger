#!/bin/sh
set -e

CERT="certs/client_cert.pem"
KEY="certs/client_key.pem"

if [ ! -f "$CERT" ] || [ ! -f "$KEY" ]; then
  echo "No OPC UA client certificate found, generating..."
  uv run python -m src.cert
else
  echo "OPC UA client certificate found"
fi

echo "Starting OPC UA client..."
exec uv run python -m src.client
