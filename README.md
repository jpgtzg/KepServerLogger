# KepServerLogger

A distributed telemetry system that uses **KepServerEX as the central data hub** to collect, route, and persist industrial and system metrics into a TimescaleDB time-series database.

---

## Overview

KepServerLogger is split into two independent applications that communicate exclusively through KepServerEX's OPC UA server:

- **Extractor** — runs on the Windows machine hosting KepServerEX. Collects local system metrics (CPU, RAM, network, services, events, OPC diagnostics) and publishes them as OPC UA nodes on KepServer.
- **Ingestor** — runs on a separate Linux machine. Connects to the same KepServer OPC UA server, reads all published data (system metrics + tag channels), and persists it into TimescaleDB.

KepServer acts as the single integration point. Neither component talks to the other directly.

---

## Data Flow

```
┌────────────────────────────────────────────────────────┐
│               Windows machine (KepServerEX)            │
│                                                        │
│  ┌─────────────┐        ┌──────────────────────────┐  │
│  │  Extractor  │─write─▶│     KepServer OPC UA     │  │
│  │  (Python    │        │                          │  │
│  │   .exe)     │        │  KepServerLogger channel │  │
│  └─────────────┘        │  ├─ Metrics.CPU          │  │
│                         │  ├─ Metrics.RAM           │  │
│  System metrics         │  ├─ Metrics.Network       │  │
│  collected locally:     │  ├─ Metrics.Services      │  │
│  ├─ CPU / RAM           │  ├─ Metrics.Events        │  │
│  ├─ Network I/O         │  └─ Metrics.OpcConnects   │  │
│  ├─ Windows services    │                          │  │
│  ├─ KepServer event log │  OPC DA channels         │  │
│  └─ opcdiags.log        │  ├─ FLS.Tags  (PLC tags) │  │
│                         │  └─ RX.Tags   (link tags) │  │
│  PLC / Link tags live   └──────────────────────────┘  │
│  natively in KepServer                                 │
└────────────────────────────────────────────────────────┘
                              │
                    OPC UA (Basic256Sha256
                    SignAndEncrypt, TCP)
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│                Linux machine (Ingestor)                 │
│                                                        │
│  ┌───────────────────────────────────────────────┐    │
│  │               Ingestor (Docker)               │    │
│  │                                               │    │
│  │  Reads from KepServer:                        │    │
│  │  ├─ Tag channels  ──▶ tags table              │    │
│  │  │  (plc_tags, link_tags, ...)                │    │
│  │  ├─ CPU           ──▶ cpu_usage table         │    │
│  │  ├─ RAM           ──▶ ram_usage table         │    │
│  │  ├─ Network       ──▶ network_usage table     │    │
│  │  ├─ Services      ──▶ services table          │    │
│  │  ├─ Events        ──▶ events table            │    │
│  │  └─ OPC Diags     ──▶ opc_connection_events  │    │
│  └───────────────────────────────────────────────┘    │
│                        │                              │
│                        ▼                              │
│              ┌──────────────────┐                     │
│              │   TimescaleDB    │                     │
│              └──────────────────┘                     │
└─────────────────────────────────────────────────────────┘
```

### Two classes of data

**1. System metrics** — produced by the extractor and published to KepServer's `KepServerLogger` channel (a Simulator driver channel). The extractor writes structured data to pre-configured UA nodes each loop iteration. The ingestor reads those same nodes and deserialises them into typed models before writing to dedicated database tables.

**2. Process tags (commonly PLC Tags)** — these live natively in KepServer, already existing and are commonly used in industrial applications. The extractor has no involvement. The ingestor reads them directly from their respective address and stores them as raw `(tag, value, status_code, timestamp)` rows in the generic `tags` table.

The key distinction: system metrics pass through the extractor before reaching KepServer; process tags originate in KepServer and are only read by the ingestor. Also, process tags are used in the field and are not intended to be modified by this system. The ingestor reads them as-is and stores them in the database.

---

## Components

### Extractor (`extractors/`)

A Python application compiled to a Windows `.exe`. On each 1-second loop tick it:

1. Reads local system metrics via `psutil` and Windows APIs.
2. Reads new OPC diagnostic events from `opcdiags.log` (incremental, byte-offset based).
3. Polls the KepServer REST API for event log entries.
4. Publishes all data to KepServer's OPC UA server as pre-configured String nodes.

Metrics published:

| Metric | UA node pattern | DB table |
|---|---|---|
| CPU usage | `KepServerLogger.Metrics.CPU.<field>` | `cpu_usage` |
| RAM usage | `KepServerLogger.Metrics.RAM.<field>` | `ram_usage` |
| Network I/O | `KepServerLogger.Metrics.Network.batch` | `network_usage` |
| Windows services | `KepServerLogger.Metrics.Services.<name>_<idx>` | `services` |
| KepServer events | `KepServerLogger.Metrics.Events.batch` | `events` |
| OPC client sessions | `KepServerLogger.Metrics.OpcConnections.batch` | `opc_connection_events` |

Batch nodes (`*.batch`) carry a JSON-encoded array. Per-field nodes carry scalar string values.

The extractor targets Windows only and is intended to run as a Windows service (e.g. via NSSM).

### KepServer (central hub)

KepServerEX serves as the message broker between the extractor and ingestor. It holds three categories of nodes relevant to this system:

- **`KepServerLogger` channel** (Simulator driver) — nodes written by the extractor and read by the ingestor for system metrics. These are part of the KepServerLogger application and are used to transmit metrics between the extractor and the ingestor. Configured via `Metrics.csv`.
- **Tag channels** (e.g. `Kepserver_OPC_DA.FLS.Tags`, `Kepserver_OPC_UA.RX.Tags`) — any number of KepServer channels or Advanced Tag groups that are not managed by KepServerLogger but rather are desired to be logged. Read directly by the ingestor. Each channel is declared in `TagList.csv` (via the `Type` column) and mapped to its OPC UA prefix in `settings.json` under `tag_channels`. Adding a new channel requires no code changes. The tags under these channels are those referred to as "process tags" in the data flow section.

All communication uses OPC UA with `Basic256Sha256 SignAndEncrypt`. Both the extractor and ingestor authenticate with a username/password and present a client certificate that must be trusted in KepServer's certificate store.

### Ingestor (`ingestors/`)

A Python asyncio application running in Docker on Linux. On each 1-second loop tick it:

1. Reads all enabled metric types from KepServer via `OPCUAClient.read_batch()` or individual node reads.
2. Deserialises each metric into its typed model.
3. Writes to TimescaleDB.

Which metrics are ingested is controlled by `metrics_to_log` in `settings.json`. The ingestor skips any metric type not listed there.

---

## Tag Configuration

- `TagList.csv`. Is used to specify the process tags that the ingestor should read from KepServer. Each row defines a tag, its source channel, and its data type. The `Type` column links the tag to a channel prefix defined in `settings.json`.  
- For system metrics or KepServerLogger's internal data, tags are configured via `settings.json` by specifying the prefix under which they are stored.

Using data from `TagList.csv` and settings.json (as system metrics are already defined in their structure), the ingestor constructs fully-qualified OPC UA node IDs by prepending the channel prefix to the tag name. This allows the ingestor to read tags from multiple channels without hardcoding their locations.

### TagList.csv

```
PI Tag name,PI tag description,Instrumenttag (address),Pointsource,PointType,Type
FM2_BElvT30W.BAL,FM2 OPTIBAT Elevator amps T30, ,OPT,Float32,plc_tags
MyLinkTag,Some advanced tag description, , ,Float32,link_tags
```

| Column | Purpose |
|---|---|
| `PI Tag name` | Tag name as it appears in the OPC DA node (`.BAL` suffix is stripped automatically) |
| `PI tag description` | Human-readable label |
| `Instrumenttag (address)` | Used for write-back tags; ignored by the ingestor |
| `Pointsource` | Source system identifier |
| `PointType` | Data type hint |
| `Type` | **Channel name.** Must match a key in `settings.json → metrics_config.tag_channels`. |

The `Type` column links a tag row to its OPC UA prefix. At startup the ingestor loads every channel defined in `tag_channels`, filters `TagList.csv` by that channel name, and prepends the corresponding prefix to build fully-qualified OPC UA node IDs. Adding a new tag source means adding rows with a new `Type` value and one entry to `tag_channels` in `settings.json` — no code changes required.

Tags containing `_Write` or `_WRITE` are automatically excluded from all channel reads (these are write-back tags, not for logging).

All process tags are stored in the same `tags` table regardless of type:

```sql
tags (server_timestamp, tag, value, status_code, source_timestamp)
```

### settings.json

Controls which metrics are active and where their OPC UA nodes live:

```json
{
    "timestamp_format": "%Y-%m-%dT%H:%M:%SZ",
    "log_retention_days": 7,
    "metrics_to_log": [
        "cpu", "ram", "network", "services",
        "kepserverevents", "tag_channels", "opcdiagnostics"
    ],
    "metrics_config": {
        "cpu":            { "prefix": "ns=2;s=KepServerLogger.Metrics.CPU" },
        "ram":            { "prefix": "ns=2;s=KepServerLogger.Metrics.RAM" },
        "network":        { "prefix": "ns=2;s=KepServerLogger.Metrics.Network" },
        "services":       { "prefix": "ns=2;s=KepServerLogger.Metrics.Services", "names": [...] },
        "kepserverevents":{ "prefix": "ns=2;s=KepServerLogger.Metrics.Events" },
        "tag_channels": {
            "plc_tags":  "ns=2;s=Kepserver_OPC_DA.FLS.Tags",
            "link_tags": "ns=2;s=Kepserver_OPC_UA.RX.Tags"
        },
        "opcdiagnostics": { "prefix": "ns=2;s=KepServerLogger.Metrics.OpcConnections",
                            "log_path": "C:\\ProgramData\\Kepware\\KEPServerEX\\V6\\opcdiags.log" }
    }
}
```

`settings.json` must be identical on both the extractor and ingestor machines — it defines the shared node namespace both sides agree on.

---

## Database Schema

| Table | Hypertable key | Description |
|---|---|---|
| `tags` | `server_timestamp` | All PLC and Link tag values (raw passthrough) |
| `cpu_usage` | `timestamp` | CPU usage percentage |
| `ram_usage` | `timestamp` | Total and free RAM in KB |
| `network_usage` | `timestamp` | Per-interface sent/received KB |
| `services` | `timestamp` | Windows service status snapshots |
| `events` | `timestamp` | KepServer event log entries |
| `opc_connection_events` | `timestamp` | OPC UA client connect/disconnect events |

All tables are TimescaleDB hypertables with a retention policy set by `log_retention_days` in `settings.json`.

---

## Deployment

### Build

**Extractor (Windows — must be built from a Windows machine):**

```powershell
# Build extractor only
.\build.ps1

# Build extractor + certgen utility
.\build.ps1 -certgen
```

**Ingestor (Linux):**

```sh
# Build and save ingestor image only
./build_ingestor.sh ingestors/Dockerfile ingestors

# Also pull and save the TimescaleDB image (for air-gapped targets)
./build_ingestor.sh --timescale ingestors/Dockerfile ingestors
```

### Files to deploy

**Windows machine (Extractor):**

| File | Notes |
|---|---|
| `extractor.exe` | Built by `build.ps1` |
| `kepserver-certgen.exe` | Optional; generates OPC UA client certificate |
| `.env` | Credentials and connection settings |
| `settings.json` | Must match the ingestor's copy |

**Linux machine (Ingestor):**

| File | Notes |
|---|---|
| `.env` | Credentials and connection settings |
| `docker-compose.yml` | Service definitions |
| `ingestor.tar.gz` | Built by `build_ingestor.sh` |
| `settings.json` | Must match the extractor's copy |
| `TagList.csv` | Process tag definitions (bind-mounted, no image rebuild needed to update) |
| `timescaledb.tar.gz` | Only needed if the target has no registry access |

Load and start on the Linux machine:

```sh
docker load -i ingestor.tar.gz
docker load -i timescaledb.tar.gz   # if applicable
docker compose up -d
```

### K3S / Kubernetes

The ingestor and TimescaleDB can also be deployed to K3S/Kubernetes using the manifests in `k8s/`.

```sh
kubectl apply -f k8s/namespace.yaml
kubectl create secret generic kepserverlogger-secret \
  -n kepserverlogger \
  --from-literal=DB_USER='postgres' \
  --from-literal=DB_PASSWORD='REPLACE_ME' \
  --from-literal=KEPSERVER_USERNAME='REPLACE_ME' \
  --from-literal=KEPSERVER_PASSWORD='REPLACE_ME'
kubectl create secret docker-registry kepserverlogger-registry \
  -n kepserverlogger \
  --docker-server=registry.local \
  --docker-username='REPLACE_ME' \
  --docker-password='REPLACE_ME' \
  --docker-email='REPLACE_ME'
kubectl apply -k .
```

See `k8s/README.md` for private registry setup, generated `ConfigMap` handling, persistent volumes, certificate persistence, and OPC UA networking notes.

### Updating TagList.csv or settings.json

Both files are bind-mounted into the container. Changes take effect on the next container restart — no image rebuild needed:

```sh
docker compose restart ingestors
```

### Updating application code

Code changes (`lib/`, `ingestors/src/`) are baked into the image. Rebuild and redeploy:

```sh
docker compose build ingestors && docker compose up -d ingestors
```

---

## OPC UA Certificates

Both the extractor and ingestor use `Basic256Sha256 SignAndEncrypt`. Each must present a client certificate that KepServer has marked as **trusted**.

- **Extractor**: generate with `kepserver-certgen.exe`, then trust the resulting certificate in KepServer's OPC UA certificate manager.
- **Ingestor**: certificates are auto-generated on first startup and stored in the `ingestors-certs` Docker volume. The generated certificate must also be trusted in KepServer.

---

## OPC Diagnostics and Client Connection Tracking

> This feature is still under development and should not be used in production yet.

KepServerEX writes all OPC UA session activity to a binary log file:

```
C:\ProgramData\Kepware\KEPServerEX\V6\opcdiags.log
```

The extractor reads this file **incrementally** using a byte-offset cursor — only bytes appended since the last tick are decoded and parsed, keeping each iteration at ~1 ms regardless of total file size. Parsed events are published to the `OpcConnections.batch` UA node; the ingestor reads and stores them in `opc_connection_events`.

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

Each stored `OpcConnectionEvent` has a SHA-256 `hash` field used for deduplication on re-publish.

### Performance

| Scenario | Old behaviour | New behaviour |
|---|---|---|
| Startup | Read entire file once | Read entire file once |
| Each subsequent tick | Re-read entire file | Read only new bytes |
| File size 200 MB | ~15 s per tick | ~1 ms per tick |

---

## Dev Notes

- The `KepServerLogger` channel in KepServer uses the **Simulator** driver. This allows defining UA nodes without a physical device.
- KepServer tag names do not allow dots. Dots in service names are replaced with underscores (e.g. `KEPServerEX 6.18 Runtime` → `KEPServerEX 6_18 Runtime`).
- `TagList.csv` uses the separator configured in `.env` (`csv_tag_separator`). Verify this matches the file's actual delimiter before deploying.
- Adding a new process tag source (a new KepServer channel or Advanced Tag group): add rows to `TagList.csv` with a new `Type` value, and add a matching entry to `tag_channels` in `settings.json`. No code changes required — the ingestor discovers channels dynamically at startup and all tag channels flow through the same `tags` table.
