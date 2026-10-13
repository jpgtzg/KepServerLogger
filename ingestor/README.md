# JSON console logs

The ingestor emits one JSON object per line to stdout. Operational messages and
exception tracebacks use the same envelope: `schema_version`, UTC `timestamp`,
`severity`, `service`, `logger`, and `message`. During each server task it also
includes `server_name` (from `servers.json`), `database`, and `host_name` (read
from OPC UA; null before connection). Server names are not parsed into plant IDs.
The extractor and the rotating `logs/app.log` retain their existing text format.

CPU, RAM and storage records include actual measurements under `data`, their
source timestamp in `data.timestamp`, and `units`. They are emitted after the
database insert succeeds, using event names `telemetry.cpu`, `telemetry.ram`, and
`telemetry.storage`. RAM fields retain their `_kb` names but are KiB; storage
fields retain `_gb` names but are GiB, matching the extractor's calculations.
Non-finite numbers are represented as JSON null.

```json
{"schema_version":1,"timestamp":"2026-10-13T15:00:01+00:00","severity":"INFO","service":"idl-ingestor","logger":"src.subscribe","message":"[CPU] Logged CPU usage","server_name":"plant-a","database":"kepserver_plant_a","host_name":"HOST-A","event":"telemetry.cpu","data":{"timestamp":"2026-10-13T15:00:00Z","usage":45.5},"units":{"usage":"percent"}}
```

Network, services, KepServer events and process tags currently retain their
summary messages inside the JSON envelope; their individual values are not yet
exported. The existing metric selection still controls CPU/RAM/storage emission.
This output does not backfill TimescaleDB history or guarantee cloud delivery:
collection, retention and queries must be configured in the platform. A crash
between database commit and logging can leave a local sample without a log.
When checking JSON, use container logs without an added timestamp prefix (for
example, omit `kubectl logs --timestamps`).

Run the logging checks from the repository root:

```bash
python3 -m unittest discover -s tests -v
```
