"""
Generates an OPC UA client certificate/key pair for every server declared in
servers.json, skipping any pair that already exists and is valid. Run by the
ingestor's entrypoint on container start, since certs can't be produced by the
Windows-only kepserver-certgen.exe on a Linux ingestor host.
"""

import asyncio
import logging
import os
import socket
from logging import getLogger
from pathlib import Path

from certgen import ensure_certificate

from lib.servers import load_servers_configs

logger = getLogger(__name__)


async def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    host_name = socket.gethostname()
    application_name = os.getenv("APPLICATION_NAME") or "KepServerLogger"

    for server in load_servers_configs():
        app_uri = f"urn:{host_name}:{application_name}:{server.name}"
        generated = await ensure_certificate(
            Path(server.cert_path), Path(server.key_path), app_uri, host_name
        )
        if generated:
            logger.info(f"[{server.name}] Generated certificate: {server.cert_path}")
        else:
            logger.info(
                f"[{server.name}] Certificate already exists and is valid: {server.cert_path}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
