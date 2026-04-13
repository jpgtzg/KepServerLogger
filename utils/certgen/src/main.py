import asyncio
import logging
import os
import socket
import sys
from logging import getLogger
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import ExtendedKeyUsageOID
from dotenv import load_dotenv

from asyncua.crypto.cert_gen import (
    check_certificate,
    dump_private_key_as_pem,
    generate_private_key,
    generate_self_signed_app_certificate,
    load_certificate,
    load_private_key,
)


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

    host_name = os.getenv("HOST_NAME") or socket.gethostname()
    app_uri = os.getenv("APP_URI") or f"urn:{host_name}:KepServerBridge"

    key_path.parent.mkdir(parents=True, exist_ok=True)

    if key_path.exists():
        key = await load_private_key(key_path)
        generate_cert = not cert_path.exists()
        if cert_path.exists():
            cert = await load_certificate(cert_path)
            generate_cert = not check_certificate(cert, app_uri, host_name)
    else:
        key = generate_private_key()
        key_path.write_bytes(dump_private_key_as_pem(key))
        generate_cert = True

    if not generate_cert:
        logger.info("Certificate already exists and is valid.")
        logger.info(f"Key:  {key_path}")
        logger.info(f"Cert: {cert_path}")
        return 0

    subject_alt_names = [
        x509.UniformResourceIdentifier(app_uri),
        x509.DNSName(host_name),
    ]

    cert = generate_self_signed_app_certificate(
        key,
        app_uri,
        {"commonName": "KepServer Bridge"},
        subject_alt_names,
        extended=[ExtendedKeyUsageOID.CLIENT_AUTH],
        days=365,
    )

    cert_path.write_bytes(cert.public_bytes(encoding=Encoding.PEM))
    logger.info("Certificate generated successfully!")
    logger.info(f"Key:  {key_path}")
    logger.info(f"Cert: {cert_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

