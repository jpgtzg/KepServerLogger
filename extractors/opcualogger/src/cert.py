import asyncio
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID
from cryptography.hazmat.primitives.serialization import Encoding
from dotenv import load_dotenv
import os

from asyncua.crypto.cert_gen import (
    generate_private_key,
    dump_private_key_as_pem,
    generate_self_signed_app_certificate,
    load_private_key,
    load_certificate,
    check_certificate
)

load_dotenv()

CERT_PATH = "certs/client_cert.pem"
KEY_PATH = "certs/client_key.pem"

APP_URI = os.getenv("APP_URI")
HOST_NAME = os.getenv("HOST_NAME")

async def main():
    key_file = Path(KEY_PATH)
    cert_file = Path(CERT_PATH)
    
    key_file.parent.mkdir(parents=True, exist_ok=True)
    
    if key_file.exists():
        key = await load_private_key(key_file)
        generate_cert = not cert_file.exists()
        if cert_file.exists():
            cert = await load_certificate(cert_file)
            generate_cert = not check_certificate(cert, APP_URI, HOST_NAME)
    else:
        key = generate_private_key()
        key_file.write_bytes(dump_private_key_as_pem(key))
        generate_cert = True
    
    if generate_cert:
        subject_alt_names = [
            x509.UniformResourceIdentifier(APP_URI),
            x509.DNSName(HOST_NAME),
        ]
        
        cert = generate_self_signed_app_certificate(
            key,
            APP_URI,
            {"commonName": "KepServer Bridge"},
            subject_alt_names,
            extended=[ExtendedKeyUsageOID.CLIENT_AUTH],
            days=365
        )
        
        cert_file.write_bytes(cert.public_bytes(encoding=Encoding.PEM))
        print("Certificate generated successfully!")
    else:
        print("Certificate already exists and is valid.")

if __name__ == "__main__":
    asyncio.run(main())
