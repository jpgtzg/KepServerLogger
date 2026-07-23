# Rebrand Considerations: KepServerLogger → Industrial Data Logger (IDL)

This document tracks what changed as part of the KepServerLogger → **Industrial Data Logger (IDL)** rename, and what must be done in the field (on each KepServerEX instance, the K3S cluster, and Grafana) before the system will work again. None of this is optional cleanup — every item below is a **breaking change** to a live external system, not just a code/doc rename.

Everything referring to the actual third-party product (**KepServerEX** / **Kepware**) was left untouched — e.g. `KEPSERVER_SERVER_URL`, `KepEvent`, `kepserverevents`, service names like `Kepware Server Runtime`, and DB name prefixes like `kepserver_pcn`/`kepserver_dmz`. Only references to this project's own name were renamed.

## 1. OPC UA node prefix (breaking — requires changes on every KepServerEX instance)

The channel/node namespace this project writes to and reads from changed:

- `KepServerLogger.Metrics.*` → `IDL.Metrics.*`
- `KepServerLogger` channel name → `IDL`

Affected: `settings.json` (root and `docs/settings.*.example.json`), `README.md`, `docs/UA-Node-Tag-Layout.csv` import instructions.

**Action required per site**, before starting the new extractor/ingestor build:

1. In each KepServerEX instance, create a new `IDL` channel (Simulator driver), importing `docs/UA-Node-Tag-Layout.csv` the same way the old `KepServerLogger` channel was created.
2. Once the new channel is confirmed working, remove the old `KepServerLogger` channel (or leave it orphaned — extractor/ingestor will simply stop writing/reading it).
3. Redeploy `settings.json` to **every** extractor machine and the ingestor at the same time — the node-address fields must match exactly on both sides (see `README.md`'s Configuration section).

Until this is done at a given site, the extractor will publish to nodes the ingestor isn't (yet) reading the same way, or vice versa, depending on which side is updated first — plan for a brief coordinated cutover per site, not a rolling one.

## 2. OPC UA client certificate Application URI (breaking — re-trust required)

`utils/certgen` derives the certificate's Application URI from `APPLICATION_NAME`, which changed:

- Extractor default: `KepServerLogger` → `IDL` (see `docs/extractor.env.example`: `APPLICATION_NAME=IDL-Extractor`)
- Ingestor default: `KepServerLogger` → `IDL` (see `docs/ingestor.env.example`: `APPLICATION_NAME=IDL`)
- Generated URI: `urn:{hostname}:KepServerLogger` → `urn:{hostname}:IDL`

Any certificate generated with the new build will have a **different Application URI**, which KepServerEX treats as a different client identity even if the hostname is unchanged.

**Action required per site**: after deploying the rebuilt extractor/ingestor, regenerate certificates (delete existing `certs/*.pem` or let the app regenerate on next boot) and **manually re-trust** the new certificate in each KepServerEX instance's OPC UA certificate manager — same as any first-boot cert trust step in `README.md` / `ingestor/k3s/README.md`.

## 3. K3S namespace and object names (breaking — requires manual namespace migration)

All k3s/Kustomize object names changed from the `kepserverlogger` prefix to `idl`:

| Old | New |
|---|---|
| Namespace `kepserverlogger` | Namespace `idl` |
| ConfigMap `kepserverlogger-env` | `idl-env` |
| Secret `kepserverlogger-secret` | `idl-secret` |
| ConfigMap `kepserverlogger-files-<hash>` | `idl-files-<hash>` |
| Secret `kepserverlogger-servers-<hash>` | `idl-servers-<hash>` |
| Image `ingestors` | `ingestor` |

Kubernetes namespaces can't be renamed in place. If a `kepserverlogger` namespace is already deployed:

1. Follow `ingestor/k3s/README.md` as if doing a fresh deployment into the new `idl` namespace (it now uses `idl`-prefixed names throughout).
2. Migrate TimescaleDB data via `pg_dump`/`pg_restore` into the new namespace's StatefulSet (same procedure the README already documents for Docker → K3S migration).
3. Once the `idl` namespace is confirmed healthy, delete the old `kepserverlogger` namespace (`kubectl delete namespace kepserverlogger`) — this also removes its Secrets/ConfigMaps/PVCs, so don't do this until data migration is verified.

## 4. Directory renames (breaking — requires rebuild, not just a checkout)

- `ingestors/` → `ingestor/`
- `extractors/` → `extractor/`

All Docker build contexts, `docker-compose.yml`, the ingestor's PyInstaller `.spec` (renamed `ingestors.spec` → `ingestor.spec`), and `build.ps1`/`build_ingestor.sh` invocations were updated to match. Any existing local `.venv`, build cache, or CI job referencing the old paths needs a clean rebuild — stale `dist/`/`build/` output under the old directory names will not be picked up automatically.

## 5. Grafana dashboard (breaking — dataset/datasource name changed)

`docs/dashboard/IDL Computer Logs V3.json` (renamed from `Kep Computer Logs V3.json`) had its panel `"dataset"` values changed from `kepserverlogger` to `idl`. This must match the actual **Postgres database name** each panel queries.

**Action required**: either rename the underlying Postgres database(s) to match, or re-point the dashboard's dataset field back to whatever database name is actually in use in your environment before re-importing it into Grafana. This file is a template/example — reconcile it against your real `db_name` values in `servers.json` either way.

## 6. Non-breaking cosmetic renames (safe, no field action needed)

- Root `README.md` title/prose: "KepServerLogger" → "Industrial Data Logger (IDL)"
- `lib/__init__.py` docstring
- `ingestor/src/main.py` startup log line
- `utils/certgen` package name (`kepserver-certgen` → `idl-certgen`) and built executable name (`kepserver-certgen.exe` → `idl-certgen.exe`) — update any deployment scripts/shortcuts that hardcode the old `.exe` filename
- `docs/assets/IDL Data Flow.drawio` (renamed from `KepServerLogger Data Flow.drawio`), diagram label text
- `docs/ingestor.env.example`'s example `DB_USER` changed from `keplogger` to `idl_logger` — cosmetic only since it's an example value, but if any real deployment literally copied this example verbatim, the Postgres role name won't match until updated on both ends.

## Rollout order (recommended)

1. Rebuild extractor/certgen on Windows (`build.ps1`) and ingestor on Linux (`build_ingestor.sh`) from the renamed directories.
2. Per site: create the new `IDL` KepServerEX channel, deploy new `settings.json` to extractor + ingestor together, restart both, trust the new certificates (items 1–2).
3. Migrate K3S deployments from the `kepserverlogger` namespace to `idl` (item 3), verifying data before deleting the old namespace.
4. Re-point/re-import the Grafana dashboard once the new database naming is settled (item 5).
