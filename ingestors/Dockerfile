FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/app/ingestors:/app/ingestors/src \
    CERT_PATH=/app/certs/client_cert.pem \
    KEY_PATH=/app/certs/client_key.pem

WORKDIR /app

RUN pip install --upgrade pip uv

# Copy dependency files first for layer caching
COPY ingestors/pyproject.toml ingestors/uv.lock /app/ingestors/

RUN cd /app/ingestors && uv sync --frozen

# Copy source
COPY lib/ /app/lib/
COPY ingestors/src/ /app/ingestors/src/
COPY utils/certgen/ /app/utils/certgen/
COPY ingestors/entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

VOLUME ["/app/certs"]

ENTRYPOINT ["/app/entrypoint.sh"]
