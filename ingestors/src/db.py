"""
Logger for ingesting data into the database.

Receives data from the OPC UA server and ingests it into the database.
"""

from lib.config import config
from lib.database import ProjectDatabase
from lib.models import PLCData, CPUUsage, NetworkUsage, RAMUsage, ServiceInfo, KepEvent
from datetime import datetime


class TagsDatabase(ProjectDatabase):
    def initialize(self) -> None:
        self.retention_days = config.log_retention_days

        print(
            f"Connecting to TimescaleDB at {config.db_host}:{config.db_port}/{config.db_name}..."
        )
        self.connect()
        self.initialize_schema(
            create_statements=[
                """
                CREATE TABLE IF NOT EXISTS tags (
                    server_timestamp    TIMESTAMPTZ NOT NULL,
                    tag                 TEXT NOT NULL,
                    value               TEXT,
                    status_code         TEXT,
                    source_timestamp    TIMESTAMPTZ
                );
                """
            ],
            indexes=[
                "CREATE INDEX IF NOT EXISTS idx_tags_tag_timestamp ON tags (tag, server_timestamp DESC);"
            ],
            hypertables=[("tags", "server_timestamp")],
        )
        print(
            f"Database initialized with {config.log_retention_days} days retention policy."
        )

    def save_many(self, rows: list[PLCData]) -> None:
        if not rows:
            return
        with self.transaction():
            self.execute_many(
                """
                INSERT INTO tags (tag, value, status_code, source_timestamp, server_timestamp)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (
                        r.tag,
                        r.value,
                        r.status_code,
                        r.source_timestamp,
                        r.server_timestamp,
                    )
                    for r in rows
                ],
            )

    def process_tag_values(self, tag_values, timestamp: datetime) -> list[PLCData]:
        rows = []
        for tag_name, data_value in tag_values:
            rows.append(
                PLCData(
                    tag=tag_name,
                    value=str(data_value.Value.Value),
                    status_code=data_value.StatusCode.name,
                    source_timestamp=data_value.SourceTimestamp,
                    server_timestamp=timestamp,
                )
            )
        return rows


class Database(ProjectDatabase):
    def initialize(self) -> None:
        self.connect()
        self.initialize_schema(
            create_statements=[
                """
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
                """,
            ],
            indexes=[
                "CREATE INDEX IF NOT EXISTS idx_cpu_timestamp ON cpu_usage (timestamp DESC);",
                "CREATE INDEX IF NOT EXISTS idx_network_timestamp ON network_usage (timestamp DESC, interface);",
                "CREATE INDEX IF NOT EXISTS idx_ram_timestamp ON ram_usage (timestamp DESC);",
                "CREATE INDEX IF NOT EXISTS idx_services_timestamp ON services (timestamp DESC, name);",
                "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events (timestamp DESC);",
            ],
            hypertables=[
                ("cpu_usage", "timestamp"),
                ("network_usage", "timestamp"),
                ("ram_usage", "timestamp"),
                ("services", "timestamp"),
                ("events", "timestamp"),
            ],
        )

    def insert_event(self, event: KepEvent) -> None:
        self.execute(
            """
            INSERT INTO events (hash, timestamp, event_name, source, message)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (hash, timestamp) DO NOTHING;
            """,
            (
                event.hash,
                event.timestamp,
                event.name,
                event.source,
                event.message,
            ),
        )

    def insert_cpu_usage(self, cpu_usage: CPUUsage) -> None:
        self.execute(
            "INSERT INTO cpu_usage (timestamp, usage) VALUES (%s, %s);",
            (cpu_usage.timestamp, cpu_usage.usage),
        )

    def insert_ram_usage(self, ram_usage: RAMUsage) -> None:
        self.execute(
            "INSERT INTO ram_usage (timestamp, total_kb, free_kb) VALUES (%s, %s, %s);",
            (ram_usage.timestamp, ram_usage.total_kb, ram_usage.free_kb),
        )

    def insert_network_metrics(self, network_usage: NetworkUsage) -> None:
        self.execute(
            """
            INSERT INTO network_usage (
                timestamp, interface, operational_status, network_interface_type, kb_bytes_sent, kb_bytes_received
            )
            VALUES (%s, %s, %s, %s, %s, %s);
            """,
            (
                network_usage.timestamp,
                network_usage.interface,
                network_usage.operational_status,
                network_usage.network_interface_type,
                network_usage.kb_bytes_sent,
                network_usage.kb_bytes_received,
            ),
        )

    def insert_service_info(self, service_info: ServiceInfo) -> None:
        self.execute(
            """
            INSERT INTO services (timestamp, name, status, service_type, machine_name, process_ids)
            VALUES (%s, %s, %s, %s, %s, %s);
            """,
            (
                service_info.timestamp,
                service_info.name,
                service_info.status,
                service_info.service_type,
                service_info.machine_name,
                ",".join(str(pid) for pid in service_info.process_ids),
            ),
        )
