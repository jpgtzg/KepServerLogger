# KepServer OPC UA Certificate Generator

This utility generates a **client private key** and a **self-signed application certificate** suitable for OPC UA client authentication against KepServer (or any OPC UA server that accepts client certs).

## Environment variables

Set these in a `.env` file next to the `.exe` (recommended) or in your shell:

- `APP_URI`: OPC UA Application URI (example: `urn:MYPC:KepServerBridge`)
- `HOST_NAME`: DNS name / host name to include in the certificate (example: `MYPC`)

If not provided:
- `HOST_NAME` defaults to the current machine hostname
- `APP_URI` defaults to `urn:{HOST_NAME}:KepServerBridge`

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

