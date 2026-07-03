# KepServerLogger

A distributed telemetry system that uses **KepServerEX as the central data hub** to collect, route, and persist industrial and system metrics into TimescaleDB time-series databases.

---

## Overview

KepServerLogger is split into two independent applications that communicate exclusively through KepServerEX's OPC UA server:

- **Extractor** — runs on each Windows machine hosting a KepServerEX instance. Collects local system metrics (CPU, RAM, network, services, events, OPC diagnostics) and publishes them as OPC UA nodes on that machine's KepServer.
- **Ingestor** — runs on a single central Linux machine. Connects concurrently to all registered KepServer instances, reads all published data (system metrics + tag channels), and persists each server's data into its own dedicated TimescaleDB database.

KepServer acts as the integration point for each site. Neither component talks to the other directly.

---

## Architecture

```
  Site A (Windows)                   Site B (Windows)
 ┌───────────────────┐              ┌───────────────────┐
 │  KepServerEX      │              │  KepServerEX      │
 │  ┌─────────────┐  │              │  ┌─────────────┐  │
 │  │  Extractor  │  │              │  │  Extractor  │  │
 │  │  (.exe)     │  │              │  │  (.exe)     │  │
 │  └──────┬──────┘  │              │  └──────┬──────┘  │
 │         │ publishes              │         │ publishes│
 │  ┌──────▼──────┐  │              │  ┌──────▼──────┐  │
 │  │  OPC UA     │  │              │  │  OPC UA     │  │
 │  │  Server     │  │              │  │  Server     │  │
 │  └─────────────┘  │              │  └─────────────┘  │
 └────────┬──────────┘              └────────┬──────────┘
          │ OPC UA (Basic256Sha256)           │ OPC UA (Basic256Sha256)
          │ SignAndEncrypt, TCP               │ SignAndEncrypt, TCP
          └──────────────┬───────────────────┘
                         │
              ┌──────────▼──────────┐
              │  Central Linux      │
              │  Machine (Ingestor) │
              │                     │
              │  asyncio.gather()   │
              │  ┌───────────────┐  │
              │  │ main(site-a)  │  │
              │  └──────┬────────┘  │
              │         │           │
              │  ┌──────▼────────┐  │
              │  │ TimescaleDB   │  │
              │  │ kepserver_a   │  │
              │  └───────────────┘  │
              │                     │
              │  ┌───────────────┐  │
              │  │ main(site-b)  │  │
              │  └──────┬────────┘  │
              │         │           │
              │  ┌──────▼────────┐  │
              │  │ TimescaleDB   │  │
              │  │ kepserver_b   │  │
              │  └───────────────┘  │
              └─────────────────────┘
```

Each server runs as an independent asyncio coroutine. A failure or reconnect on one server has no effect on the others.

---

## Two Classes of Data

**System metrics** — produced by the extractor and published to each KepServer's `KepServerLogger` channel (Simulator driver). The extractor writes structured data to pre-configured UA nodes each loop iteration. The ingestor reads those same nodes and deserialises them into typed models before writing to dedicated database tables.

**Process tags (PLC/Link tags)** — these live natively in KepServer. The extractor has no involvement. The ingestor reads them directly from their OPC UA address and stores them as raw `(tag, value, status_code, timestamp)` rows in the `tags` table. These tags are used in the field and are not modified by this system.

---

## Components

### Extractor (`extractors/`)

A Python application compiled to a Windows `.exe`. Runs on each KepServer machine. On each polling tick it:

1. Reads local system metrics via `psutil` and Windows APIs.
2. Reads new OPC diagnostic events from `opcdiags.log` (incremental, byte-offset based).
3. Polls the KepServer REST API for event log entries.
4. Publishes all data as OPC UA nodes to the local KepServer.
5. Publishes the machine's hostname to `KepServerLogger.Metrics.host_name`.

| Metric | UA node pattern | DB table |
|---|---|---|
| CPU usage | `KepServerLogger.Metrics.CPU.<field>` | `cpu_usage` |
| RAM usage | `KepServerLogger.Metrics.RAM.<field>` | `ram_usage` |
| Network I/O | `KepServerLogger.Metrics.Network.batch` | `network_usage` |
| Windows services | `KepServerLogger.Metrics.Services.<name>` | `services` |
| KepServer events | `KepServerLogger.Metrics.Events.batch` | `events` |
| OPC client sessions | `KepServerLogger.Metrics.OpcConnections.batch` | `opc_connection_events` |
| Hostname | `KepServerLogger.Metrics.host_name` | `connection_log` |

Batch nodes (`*.batch`) carry a JSON-encoded array. Per-field nodes carry scalar string values.

The extractor targets Windows only and is intended to run as a Windows service (e.g. via NSSM).

---

### KepServer (per-site hub)

KepServerEX is the message broker between the extractor and the ingestor at each site. It holds:

- **`KepServerLogger` channel** (Simulator driver) — nodes written by the extractor and read by the ingestor for system metrics. Configured via `docs/UA-Node-Tag-Layout.csv`.
- **Tag channels** (e.g. `Kepserver_OPC_DA.FLS.Tags`) — any KepServer channels or Advanced Tag groups whose tags should be logged. Read directly by the ingestor.

All communication uses OPC UA with `Basic256Sha256 SignAndEncrypt`. Both extractor and ingestor authenticate with username/password and present a client certificate that must be trusted in KepServer's certificate store.

`docs/UA-Node-Tag-Layout.csv` is a ready-made KepServerEX Simulator driver import for the `KepServerLogger` channel — it defines the string tags (`CPU.usage`, `RAM.free_kb`, `Network.batch`, etc.) at the addresses (`S0000`, `S0001`, ...) that the extractor writes to and the ingestor reads from. Import it directly into a new `KepServerLogger` channel/device rather than creating the tags by hand. The node names/addresses can technically be changed as long as `settings.json → metrics_config` prefixes are updated to match, but it's much easier to keep the provided layout as-is across every site than to keep a custom layout in sync.

---

### Ingestor (`ingestors/`)

A Python asyncio application running in Docker on the central Linux machine. It connects to all KepServer instances concurrently and independently:

- Each connection runs in its own coroutine (`main(server)`).
- Each server writes to its own dedicated TimescaleDB database (configured via `db_name` in `servers.json`).
- On startup the ingestor reads the hostname published by the extractor and logs a `connected` event to `connection_log`. This records which physical machine answered the connection — useful in manually-clustered environments where a failover means the same IP is served by a different host.
- If a connection drops, the ingestor logs a `disconnected` event, waits with exponential backoff (5 → 10 → 20 → 40 → 60s), and retries. The other servers are unaffected.
- On reconnect, a new `connected` event is written with the current hostname — allowing you to see whether the same or a different machine came back.

---

## Configuration

Configuration is split across three files to separate concerns. `.env` is **not shared** — the extractor and ingestor each have their own, with different fields, backed by separate config models (`ExtractorConfig` and `IngestorConfig` in `lib/config.py`):

| File | Scope | Contains |
|---|---|---|
| `servers.json` | Ingestor only | OPC UA URL, credentials, certs, DB name, CSV tag file — one entry per KepServer instance |
| `.env` (extractor) | Per extractor machine | KepServer connection URL/credentials, client cert/key paths, application name |
| `.env` (ingestor) | Ingestor only | DB host/port/user/password, application name |
| `settings.json` | Shared behaviour | Polling interval, retention days, which metrics to log, OPC UA node prefixes |

`settings.json` should be kept the same on every extractor and on the ingestor, since it defines the shared node namespace both sides agree on. Strictly, only the OPC UA node-address fields (`metrics_config.*.prefix`, `tag_channels`) and `metrics_to_log` need to match exactly — `metrics_config.services.names` and `metrics_config.opcdiagnostics.log_path` are read only by the extractor and can legitimately differ per machine (e.g. different installed services or a different KepServer install path). It's still easiest to keep one copy of the file everywhere and only vary those two fields when a machine genuinely needs it.

`servers.json` and both `.env` files are gitignored. See `docs/servers.example.json`, `docs/settings.extractor.example.json`, `docs/settings.ingestor.example.json`, `docs/extractor.env.example`, and `docs/ingestor.env.example` for templates. Protect all of them with `chmod 600`.

### servers.json

Declares the list of KepServer instances the ingestor connects to:

```json
[
    {
        "name": "plant-a",
        "url": "opc.tcp://192.168.1.100:49320",
        "username": "administrator",
        "password": "your-password",
        "db_name": "kepserver_plant_a",
        "cert_path": "certs/plant_a_client_cert.pem",
        "key_path": "certs/plant_a_client_key.pem",
        "csv_filename": "tags/plant_a_tags.csv",
        "csv_tag_column_name": "Tag Name",
        "csv_tag_separator": ","
    }
]
```

`cert_path`, `key_path`, and `csv_filename` are resolved relative to the ingestor's working directory (`/app/ingestors` inside the container), not relative to `servers.json` itself. Under Docker Compose, put each server's tag CSV in a `tags/` directory next to `docker-compose.yml` (bind-mounted to `/app/ingestors/tags`) and reference it as `tags/<file>.csv`, as in the example above.

### .env (extractor)

Deployed next to `extractor.exe` on each KepServer machine. Read by `ExtractorConfig`:

```env
APPLICATION_NAME=KepServerLogger

KEPSERVER_SERVER_URL=opc.tcp://localhost:49320
KEPSERVER_USERNAME=administrator
KEPSERVER_PASSWORD=your-kepserver-password
KEPSERVER_EVENT_LOG_URL=https://localhost:57573/config/v1/project/services/EventLog

CERT_PATH=extractor_cert.pem
KEY_PATH=extractor_key.pem
```

Loaded relative to the executable, not the current working directory, so it works regardless of what launches the `.exe` (e.g. NSSM).

### .env (ingestor)

Global infrastructure config for the central ingestor, shared across all server connections. Read by `IngestorConfig`:

```env
APPLICATION_NAME=KepServerLogger

DB_HOST=localhost
DB_PORT=5432
DB_USER=keplogger
DB_PASSWORD=your-db-password
```

### settings.json

Controls which metrics are active and where their OPC UA nodes live. See `docs/settings.extractor.example.json` (deploy next to `extractor.exe`) and `docs/settings.ingestor.example.json` (deploy on the ingestor) for the full structure — the two are identical except that `metrics_config.services.names` and `metrics_config.opcdiagnostics.log_path` are only meaningful on the extractor's copy.

---

## Tag Configuration

Process tags are declared in a CSV file per server (path set by `csv_filename` in `servers.json`). The `Type` column links each tag to a channel prefix defined in `settings.json → metrics_config.tag_channels`.

```
PI Tag name,PI tag description,Instrumenttag (address),Pointsource,PointType,Type
FM2_BElvT30W.BAL,FM2 OPTIBAT Elevator amps T30, ,OPT,Float32,plc_tags
MyLinkTag,Some advanced tag description, , ,Float32,link_tags
```

| Column | Purpose |
|---|---|
| `PI Tag name` | Tag name as it appears in the OPC DA node (`.BAL` suffix is stripped automatically) |
| `Type` | Channel name — must match a key in `settings.json → metrics_config.tag_channels` |

Tags containing `_Write` or `_WRITE` are automatically excluded (write-back tags, not for logging).

Adding a new tag source: add rows with a new `Type` value and one entry to `tag_channels` in `settings.json`. No code changes required.

---

## Database Schema

Each KepServer instance writes to its own database (named by `db_name` in `servers.json`). All databases share the same schema:

| Table | Hypertable key | Description |
|---|---|---|
| `tags` | `server_timestamp` | All process tag values (raw passthrough) |
| `cpu_usage` | `timestamp` | CPU usage percentage |
| `ram_usage` | `timestamp` | Total and free RAM in KB |
| `network_usage` | `timestamp` | Per-interface sent/received KB |
| `services` | `timestamp` | Windows service status snapshots |
| `events` | `timestamp` | KepServer event log entries |
| `opc_connection_events` | `timestamp` | OPC UA client connect/disconnect events from opcdiags.log |
| `connection_log` | `timestamp` | Ingestor-side connect/disconnect events with hostname |

All tables are TimescaleDB hypertables with a retention policy set by `log_retention_days` in `settings.json`.

### connection_log

Records when the ingestor established or lost a connection to each server:

| Column | Description |
|---|---|
| `timestamp` | UTC time of the event |
| `event` | `'connected'` or `'disconnected'` |
| `host_name` | Hostname of the KepServer machine at connect time; `null` on disconnect |
| `reason` | Error message on disconnect; `null` on connect |

Querying `connection_log` lets you see when a server went down, how long it was unreachable, and whether it came back on the same physical machine (relevant in manually-clustered environments).

---

## Deployment

### What runs where

**Each KepServer machine (Windows):**
- Extractor (`.exe`) — collects and publishes metrics to the local KepServer
- Runs as a Windows service (NSSM recommended)
- Has its own OPC UA client certificate trusted in the local KepServer

**Central ingestor machine (Linux):**
- Ingestor (Docker) — connects to all KepServer instances concurrently
- TimescaleDB (Docker) — one database per server
- One OPC UA client certificate per KepServer instance (path set in `servers.json`)

### Build

**Extractor (must be built on Windows):**

```powershell
.\build.ps1           # extractor only
.\build.ps1 -certgen  # extractor + certificate generator utility
```

**Ingestor (Linux):**

```sh
./build_ingestor.sh ingestors/Dockerfile ingestors
./build_ingestor.sh --timescale ingestors/Dockerfile ingestors  # also saves TimescaleDB image
```

### Files to deploy

**Each Windows machine (Extractor):**

| File | Notes |
|---|---|
| `extractor.exe` | Built by `build.ps1` |
| `kepserver-certgen.exe` | Generates the OPC UA client certificate |
| `.env` | Credentials and KepServer connection settings |
| `settings.json` | Node prefixes and `metrics_to_log` must match the ingestor's copy; `services.names`/`opcdiagnostics.log_path` may differ per machine |

**Central Linux machine (Ingestor):**

| File | Notes |
|---|---|
| `.env` | DB credentials and global app config |
| `servers.json` | List of KepServer instances (`chmod 600`) |
| `settings.json` | Node prefixes and `metrics_to_log` must match every extractor's copy |
| `docker-compose.yml` | Service definitions |
| `ingestor.tar.gz` | Built by `build_ingestor.sh` |
| `timescaledb.tar.gz` | Only needed without registry access |
| `tags/<server>.csv` | Process tag definitions per server — referenced from `servers.json` as `tags/<server>.csv`; the `tags/` directory is bind-mounted into the container |
| `certs/` | Bind-mounted (read-write) into the container; the ingestor auto-generates each server's client cert/key pair here on first boot if missing — see [OPC UA Certificates](#opc-ua-certificates) |

`docker-compose.yml` (`ingestors/docker-compose.yml` in the repo) — the volume mounts are load-bearing, the app looks for each file at exactly these container paths (all relative to the ingestor's working directory, `/app/ingestors`):

```yaml
version: "3.9"

services:
    timescaledb:
        image: timescale/timescaledb:latest-pg16
        container_name: timescaledb
        restart: unless-stopped
        environment:
            POSTGRES_USER: ${DB_USER}
            POSTGRES_PASSWORD: ${DB_PASSWORD}
        volumes:
            - timescaledb-data:/var/lib/postgresql/data
        ports:
            - "5432:5432"
        healthcheck:
            test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d postgres"]
            interval: 5s
            timeout: 5s
            retries: 10

    ingestors:
        build:
            context: ..
            dockerfile: ingestors/Dockerfile
        image: ingestors
        container_name: ingestors
        network_mode: host
        restart: unless-stopped
        stdin_open: true
        tty: true
        depends_on:
            timescaledb:
                condition: service_healthy
        env_file:
            - .env
        volumes:
            - ./servers.json:/app/ingestors/servers.json:ro,Z
            - ./settings.json:/app/ingestors/settings.json:ro,Z
            - ./tags:/app/ingestors/tags:ro,Z
            - ./certs:/app/ingestors/certs:Z
            - ./logs:/app/ingestors/logs

volumes:
    timescaledb-data:
```

Notes on the mounts:
- `certs` is mounted **read-write** (`:Z`, not `:ro,Z`) — the container generates missing per-server certificates into it on boot (see [OPC UA Certificates](#opc-ua-certificates)). Mounting it read-only will make certificate generation fail.
- `DB_NAME` is intentionally not referenced anywhere in this file — each server's database is created automatically by the ingestor from `servers.json`'s `db_name`, so `timescaledb` only needs `DB_USER`/`DB_PASSWORD` to bootstrap.
- If you're adding this ingestor alongside an **already-running** deployment (e.g. testing a new version side by side with production), drop the whole `timescaledb:` service and `depends_on:` block instead of running a second Postgres — point `.env`'s `DB_HOST`/`DB_PORT` at the existing instance (`localhost:5432` works if both containers use `network_mode: host`) and use distinct `image`/`container_name` values so they don't collide with the running stack.

Load and start:

```sh
docker load -i ingestor.tar.gz
docker load -i timescaledb.tar.gz   # if applicable
docker compose up -d
```

### First-boot checklist

Before the first `docker compose up -d`, on the ingestor machine's deployment directory:

1. `servers.json` exists and every entry uses the exact field name `csv_filename` (not `csv_file_name`) — the ingestor fails fast with a pydantic validation error if it's misspelled.
2. `tags/` directory exists and contains each server's CSV, matching the `tags/<file>.csv` path used in `servers.json`.
3. `certs/` directory exists (even empty) — the container will populate it with a generated cert/key pair per server on first boot. You do **not** need to pre-generate these; there's no Windows machine involved on the ingestor side.
4. `DB_USER` in `.env` has `CREATEDB` privileges on the target Postgres role — needed for the ingestor to auto-create each server's database on first connect.
5. After the first successful boot, check the logs for `Generated certificate: certs/<file>.pem` per server, then **manually trust each generated certificate** in that server's respective KepServer OPC UA certificate manager — this step can't be automated from the ingestor side.

### Updating configuration

`servers.json`, `settings.json`, and CSV tag files are bind-mounted into the container. Changes take effect on restart — no image rebuild:

```sh
docker compose restart ingestors
```

Code changes (`lib/`, `ingestors/src/`) require a rebuild:

```sh
docker compose build ingestors && docker compose up -d ingestors
```

---

## OPC UA Certificates

Both extractor and ingestor use `Basic256Sha256 SignAndEncrypt`. Each client must present a certificate trusted in that KepServer's certificate store.

- **Extractor**: generate with `kepserver-certgen.exe`, then trust the certificate in the local KepServer's OPC UA certificate manager.
- **Ingestor**: one certificate pair per server, paths declared in `servers.json`. Since the ingestor runs on Linux, it can't use the Windows-only `kepserver-certgen.exe` — instead, the container generates any missing certificate/key pair for each configured server automatically on startup (see `utils/certgen/src/generate_server_certs.py`, run by `ingestors/entrypoint.sh`), writing them to the paths declared in `servers.json`. You still need to manually trust each generated certificate in that server's respective KepServer certificate manager after the container's first boot.

---

## OPC Diagnostics and Client Connection Tracking

KepServerEX writes all OPC UA session activity to a binary log file:

```
C:\ProgramData\Kepware\KEPServerEX\V6\opcdiags.log
```

The extractor reads this file **incrementally** using a byte-offset cursor — only bytes appended since the last tick are decoded, keeping each iteration at ~1 ms regardless of file size. Parsed events are published to the `OpcConnections.batch` UA node and stored in `opc_connection_events`.

### Event structure

The file is UTF-16-LE encoded. Each event follows this pattern:

```
[<session-tag>]  <EventType>
0:  Event started
0000000000: timestamp (UTC): 2026-04-30T10:23:01.456
0000000000: applicationName: OPC Foundation|UA .NET Standard
...
0:  Event complete
```

Human-readable client names are resolved from `CreateSessionRequest` events. A `tag → name` map persists across loop iterations so that a `CloseSessionRequest` in a later tick can still resolve the name established earlier. Tags `NoSession`, `AnonymousClient`, and `opc.tcp://…` URLs are skipped (internal KepServer actors).

Each stored `OpcConnectionEvent` has a SHA-256 `hash` field for deduplication.

---

## Dev Notes

- The `KepServerLogger` channel in KepServer uses the **Simulator** driver, which allows defining UA nodes without a physical device.
- KepServer tag names do not allow dots. Dots in service names are replaced with underscores.
- `settings.json` must be kept in sync between all extractors and the ingestor for the node-address fields (`metrics_config.*.prefix`, `tag_channels`) and `metrics_to_log` — these define the shared OPC UA node namespace. `metrics_config.services.names` and `metrics_config.opcdiagnostics.log_path` are extractor-only and can differ per machine.
- Adding a new KepServer instance: add an entry to `servers.json`, deploy its cert to the ingestor machine, and restart the ingestor. No code changes required — the ingestor creates the target database (and enables the `timescaledb` extension) on first connect if it doesn't already exist, as long as `DB_USER` has `CREATEDB` privileges.
- The ingestor retries dropped connections with exponential backoff (5 → 10 → 20 → 40 → 60s). Each reconnect attempt is independent per server. Connection history is recorded in `connection_log`.
- The extractor and ingestor each read their own `.env` into a dedicated Pydantic settings model (`ExtractorConfig` / `IngestorConfig` in `lib/config.py`) — they have no fields in common, so don't copy one machine's `.env` to the other.
