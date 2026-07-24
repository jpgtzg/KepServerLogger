FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/app/ingestor:/app/ingestor/src

WORKDIR /app

RUN pip install --upgrade pip uv

# Copy dependency files first for layer caching
COPY ingestor/pyproject.toml ingestor/uv.lock /app/ingestor/

RUN cd /app/ingestor && uv sync --frozen

# Copy source
COPY lib/ /app/lib/
COPY ingestor/src/ /app/ingestor/src/
COPY utils/certgen/ /app/utils/certgen/
COPY ingestor/entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
