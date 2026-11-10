"""
Logger for ingesting data into the database.

Receives data from the OPC UA server and ingests it into the database.
"""

import traceback
import uuid
from datetime import UTC, datetime
from logging import getLogger

from lib.database import ProjectDatabase

logger = getLogger(__name__)


class IngestorDatabase(ProjectDatabase):
    def initialize(self) -> None:
        logger.info(
            f"Connecting to TimescaleDB at {self._host}:{self._port}/{self._db_name}..."
        )
        self.ensure_database_exists()
        self.connect()
        self.initialize_schema(
            create_statements=[
                """
                CREATE EXTENSION IF NOT EXISTS timescaledb;

                CREATE TABLE IF NOT EXISTS tags (
                    logger_timestamp    TIMESTAMPTZ NOT NULL,
                    address             TEXT NOT NULL,
                    tag                 TEXT NOT NULL,
                    value               TEXT,
                    status_code         TEXT,
                    source_timestamp    TIMESTAMPTZ,
                    server_timestamp    TIMESTAMPTZ
                );

                ALTER TABLE tags ADD COLUMN IF NOT EXISTS address TEXT NOT NULL DEFAULT '';

                CREATE TABLE IF NOT EXISTS events (
                    hash        TEXT NOT NULL,
                    timestamp   TIMESTAMPTZ NOT NULL,
                    event_name  TEXT NOT NULL,
                    source      TEXT NOT NULL,
                    message     TEXT NOT NULL,
                    PRIMARY KEY (hash, timestamp)
                );

                CREATE TABLE IF NOT EXISTS cpu_usage (
                    timestamp   TIMESTAMPTZ NOT NULL,
                    usage       REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS network_usage (
                    timestamp               TIMESTAMPTZ NOT NULL,
                    interface               TEXT NOT NULL,
                    operational_status      TEXT NOT NULL,
                    network_interface_type  TEXT NOT NULL,
                    kb_bytes_sent           REAL NOT NULL,
                    kb_bytes_received       REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ram_usage (
                    timestamp   TIMESTAMPTZ NOT NULL,
                    total_kb    BIGINT NOT NULL,
                    free_kb     BIGINT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS services (
                    timestamp       TIMESTAMPTZ NOT NULL,
                    name            TEXT NOT NULL,
                    status          TEXT NOT NULL,
                    service_type    TEXT NOT NULL,
                    machine_name    TEXT NOT NULL,
                    process_ids     TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS heartbeat_rtt (
                    timestamp   TIMESTAMPTZ NOT NULL,
                    pair        TEXT NOT NULL,
                    value       INTEGER NOT NULL,
                    rtt_ms      DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (pair, value, timestamp)
                );

                CREATE TABLE IF NOT EXISTS agent_logs (
                    timestamp   TIMESTAMPTZ NOT NULL,
                    level       TEXT NOT NULL,
                    component   TEXT NOT NULL,
                    message     TEXT NOT NULL,
                    traceback   TEXT,
                    PRIMARY KEY (timestamp, component, message)
                );

                CREATE TABLE IF NOT EXISTS active_log (
                    timestamp   TIMESTAMPTZ NOT NULL,
                    event       TEXT NOT NULL,
                    host_name   TEXT,
                    reason      TEXT,
                    error_id    TEXT
                );

                CREATE TABLE IF NOT EXISTS ingestor_logs (
                    id          TEXT NOT NULL,
                    timestamp   TIMESTAMPTZ NOT NULL,
                    level       TEXT NOT NULL,
                    component   TEXT NOT NULL,
                    message     TEXT NOT NULL,
                    traceback   TEXT,
                    PRIMARY KEY (id, timestamp)
                );

                CREATE TABLE IF NOT EXISTS storage_usage (
                    timestamp   TIMESTAMPTZ NOT NULL,
                    total_gb    REAL NOT NULL,
                    used_gb     REAL NOT NULL,
                    free_gb     REAL NOT NULL
                );
                """
            ],
            indexes=[
                "CREATE INDEX IF NOT EXISTS idx_tags_address_tag_timestamp ON tags (address, tag, logger_timestamp DESC);",
                "CREATE INDEX IF NOT EXISTS idx_cpu_timestamp ON cpu_usage (timestamp DESC);",
                "CREATE INDEX IF NOT EXISTS idx_network_timestamp ON network_usage (timestamp DESC, interface);",
                "CREATE INDEX IF NOT EXISTS idx_ram_timestamp ON ram_usage (timestamp DESC);",
                "CREATE INDEX IF NOT EXISTS idx_storage_timestamp ON storage_usage (timestamp DESC);",
                "CREATE INDEX IF NOT EXISTS idx_services_timestamp ON services (timestamp DESC, name);",
                "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events (timestamp DESC);",
                "CREATE INDEX IF NOT EXISTS idx_heartbeat_rtt_timestamp ON heartbeat_rtt (timestamp DESC, pair);",
                "CREATE INDEX IF NOT EXISTS idx_agent_logs_timestamp ON agent_logs (timestamp DESC, level);",
                "CREATE INDEX IF NOT EXISTS idx_active_log_timestamp ON active_log (timestamp DESC);",
                "CREATE INDEX IF NOT EXISTS idx_active_log_error_id ON active_log (error_id);",
                "CREATE INDEX IF NOT EXISTS idx_ingestor_logs_timestamp ON ingestor_logs (timestamp DESC, level);",
                "CREATE INDEX IF NOT EXISTS idx_ingestor_logs_id ON ingestor_logs (id);",
            ],
            hypertables=[
                ("tags", "logger_timestamp"),
                ("cpu_usage", "timestamp"),
                ("network_usage", "timestamp"),
                ("ram_usage", "timestamp"),
                ("storage_usage", "timestamp"),
                ("services", "timestamp"),
                ("events", "timestamp"),
                ("heartbeat_rtt", "timestamp"),
                ("agent_logs", "timestamp"),
                ("active_log", "timestamp"),
                ("ingestor_logs", "timestamp"),
            ],
        )
        logger.info(
            f"Database initialized with {self.retention_days} days retention policy."
        )

    def insert_many(self, rows_by_table: dict[str, list[dict[str, object]]]) -> None:
        """
        Writes rows to several tables in one transaction. Each table maps to its rows,
        a dict of column -> value with the same columns throughout. A row the table
        already has (same primary key) is skipped, which is how the republished
        event list is deduplicated.
        """
        statements = []
        for table, rows in rows_by_table.items():
            if not rows:
                continue
            columns = list(rows[0])
            for identifier in (table, *columns):
                self._validate_identifier(identifier)
            query = (
                f"INSERT INTO {table} ({', '.join(columns)}) "
                f"VALUES ({', '.join(['%s'] * len(columns))}) ON CONFLICT DO NOTHING;"
            )
            statements.append((query, [tuple(r[c] for c in columns) for r in rows]))
        if not statements:
            return
        with self.transaction():
            for query, params in statements:
                self.execute_many(query, params)

    def log_status(
        self,
        event: str,
        *,
        host_name: str | None = None,
        reason: str | None = None,
        error_id: str | None = None,
    ) -> None:
        """
        Records the ingestor's connection state: 'active' while it holds a live
        OPC UA session, 'inactive' whenever that session ends (shutdown or a
        fatal error that forces a reconnect). `error_id` links an 'inactive'
        row to the `ingestor_logs` row (see `log_event`) that explains why,
        instead of duplicating the exception message here.
        """
        with self.transaction():
            self.execute(
                """
                INSERT INTO active_log (timestamp, event, host_name, reason, error_id)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (datetime.now(UTC), event, host_name, reason, error_id),
            )

    def log_event(self, level: str, component: str, exc: BaseException) -> str:
        """
        Records an error/warning that was otherwise only sent to the log file
        (e.g. a per-metric read that was skipped rather than treated as a full
        disconnect), so it can be queried later without needing the raw logs.
        Returns the generated row id so callers can cross-reference it, e.g.
        from `active_log.error_id`.
        """
        event_id = str(uuid.uuid4())
        with self.transaction():
            self.execute(
                """
                INSERT INTO ingestor_logs (id, timestamp, level, component, message, traceback)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (
                    event_id,
                    datetime.now(UTC),
                    level,
                    component,
                    f"{type(exc).__name__}: {exc}",
                    "".join(
                        traceback.format_exception(type(exc), exc, exc.__traceback__)
                    ),
                ),
            )
        return event_id
