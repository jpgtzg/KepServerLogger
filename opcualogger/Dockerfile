FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN pip install --upgrade pip && \
    pip install uv

COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen

COPY . /app

VOLUME ["/app/certs"]

ENTRYPOINT ["/app/entrypoint.sh"]
