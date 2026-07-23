#!/bin/sh
set -e

echo "Ensuring OPC UA client certificates for all configured servers..."
cd /app/ingestor && uv run python /app/utils/certgen/src/generate_server_certs.py

echo "Starting ingestor..."
cd /app/ingestor && exec uv run python src/main.py
