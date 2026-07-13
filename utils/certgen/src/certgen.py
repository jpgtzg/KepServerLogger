from logging import getLogger
from pathlib import Path

from asyncua.crypto.cert_gen import (
    check_certificate,
    dump_private_key_as_pem,
    generate_private_key,
    generate_self_signed_app_certificate,
    load_certificate,
    load_private_key,
)
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import ExtendedKeyUsageOID

logger = getLogger(__name__)


async def ensure_certificate(
    cert_path: Path, key_path: Path, app_uri: str, host_name: str
) -> bool:
    """
    Ensures a valid OPC UA client cert/key pair exists at the given paths,
    generating a new self-signed pair if missing or invalid for app_uri/host_name.
    Returns True if a new pair was generated.
    """
    key_path.parent.mkdir(parents=True, exist_ok=True)
    cert_path.parent.mkdir(parents=True, exist_ok=True)

    if key_path.exists():
        key = await load_private_key(key_path)
        generate_cert = not cert_path.exists()
        if cert_path.exists():
            cert = await load_certificate(cert_path)
            generate_cert = check_certificate(cert, app_uri, host_name)
    else:
        key = generate_private_key()
        key_path.write_bytes(dump_private_key_as_pem(key))
        generate_cert = True

    if not generate_cert:
        return False

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
    return True
