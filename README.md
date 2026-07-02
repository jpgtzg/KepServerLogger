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

- **`KepServerLogger` channel** (Simulator driver) — nodes written by the extractor and read by the ingestor for system metrics. Configured via `Metrics.csv`.
- **Tag channels** (e.g. `Kepserver_OPC_DA.FLS.Tags`) — any KepServer channels or Advanced Tag groups whose tags should be logged. Read directly by the ingestor.

All communication uses OPC UA with `Basic256Sha256 SignAndEncrypt`. Both extractor and ingestor authenticate with username/password and present a client certificate that must be trusted in KepServer's certificate store.

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

Configuration is split across three files to separate concerns:

| File | Scope | Contains |
|---|---|---|
| `servers.json` | Per server | OPC UA URL, credentials, certs, DB name, CSV tag file |
| `.env` | Global infra | DB host/port/user/password, OPC UA app URI, application name |
| `settings.json` | Shared behaviour | Polling interval, retention days, which metrics to log, OPC UA node prefixes |

`settings.json` must be identical on every extractor and on the ingestor — it defines the shared node namespace both sides agree on.

`servers.json` and `.env` are gitignored. See `docs/servers.example.json` and `docs/settings.example.json` for templates. Protect both with `chmod 600`.

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

### .env

Global infrastructure config shared across all server connections:

```env
APPLICATION_NAME=KepServerLogger

DB_HOST=localhost
DB_PORT=5432
DB_USER=keplogger
DB_PASSWORD=your-db-password
```

### settings.json

Controls which metrics are active and where their OPC UA nodes live. See `docs/settings.example.json` for the full structure.

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
| `settings.json` | Must match the ingestor's copy |

**Central Linux machine (Ingestor):**

| File | Notes |
|---|---|
| `.env` | DB credentials and global app config |
| `servers.json` | List of KepServer instances (`chmod 600`) |
| `settings.json` | Must match every extractor's copy |
| `docker-compose.yml` | Service definitions |
| `ingestor.tar.gz` | Built by `build_ingestor.sh` |
| `timescaledb.tar.gz` | Only needed without registry access |
| `tags/<server>.csv` | Process tag definitions per server |
| `certs/<server>_cert.pem` | OPC UA client cert per server |
| `certs/<server>_key.pem` | OPC UA client key per server |

Load and start:

```sh
docker load -i ingestor.tar.gz
docker load -i timescaledb.tar.gz   # if applicable
docker compose up -d
```

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
- **Ingestor**: one certificate pair per server, paths declared in `servers.json`. Certificates can be generated with the same `kepserver-certgen.exe` utility and must be trusted in each respective KepServer.

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
- `settings.json` must be kept in sync between all extractors and the ingestor — it defines the shared OPC UA node namespace.
- Adding a new KepServer instance: add an entry to `servers.json`, create its database, deploy its cert to the ingestor machine, and restart the ingestor. No code changes required.
- The ingestor retries dropped connections with exponential backoff (5 → 10 → 20 → 40 → 60s). Each reconnect attempt is independent per server. Connection history is recorded in `connection_log`.
