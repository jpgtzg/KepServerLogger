import asyncio
import logging
import os
import socket
import sys
from logging import getLogger
from pathlib import Path

from dotenv import load_dotenv

from certgen import ensure_certificate


def _base_dir() -> Path:
    """
    Directory where outputs/config should live.
    - In a PyInstaller .exe: alongside the executable
    - In source: alongside this project (utils/certgen/)
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "executable"):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _load_env(base_dir: Path) -> None:
    # Prefer a .env next to the exe, but still allow shell env vars.
    load_dotenv(base_dir / ".env", override=False)
    load_dotenv(override=False)


logger = getLogger(__name__)


async def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    base_dir = _base_dir()
    _load_env(base_dir)

    cert_path = Path(os.getenv("CERT_PATH") or base_dir / "certs" / "client_cert.pem")
    key_path = Path(os.getenv("KEY_PATH") or base_dir / "certs" / "client_key.pem")

    host_name = socket.gethostname()
    application_name = os.getenv("APPLICATION_NAME") or "IDL"
    app_uri = f"urn:{host_name}:{application_name}"

    generated = await ensure_certificate(cert_path, key_path, app_uri, host_name)

    if not generated:
        logger.info("Certificate already exists and is valid.")
    else:
        logger.info("Certificate generated successfully!")
    logger.info(f"Key:  {key_path}")
    logger.info(f"Cert: {cert_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
