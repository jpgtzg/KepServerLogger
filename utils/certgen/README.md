# KepServer OPC UA Certificate Generator

This utility generates a **client private key** and a **self-signed application certificate** suitable for OPC UA client authentication against KepServer (or any OPC UA server that accepts client certs).

## Environment variables

The following paths can be overridden via `.env` or shell:

- `CERT_PATH`: output path for the certificate (default: `certs/client_cert.pem` next to the exe)
- `KEY_PATH`: output path for the private key (default: `certs/client_key.pem` next to the exe)

The OPC UA Application URI and DNS SAN are derived automatically from the machine hostname:
- URI: `urn:{hostname}:KepServerLogger`
- DNS SAN: `{hostname}`

## Output

The executable writes into a `certs/` folder next to itself:

- `certs/client_key.pem`
- `certs/client_cert.pem`

## Build (local)

From `utils/certgen/`:

```powershell
uv sync
uv run pyinstaller certgen.spec --noconfirm --clean
```

The `.exe` will be created under `utils/certgen/dist/`.
