from __future__ import annotations

from lib.database import ProjectDatabase
from models import KepEvent, ServiceInfo


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
                self.utcnow(),
                event.name,
                event.source,
                event.message,
            ),
        )

    def insert_cpu_usage(self, cpu_usage: float) -> None:
        self.execute(
            "INSERT INTO cpu_usage (timestamp, usage) VALUES (%s, %s);",
            (self.utcnow(), cpu_usage),
        )

    def insert_network_metrics(
        self,
        interface: str,
        operational_status: str,
        network_interface_type: str,
        kb_bytes_sent: float,
        kb_bytes_received: float,
    ) -> None:
        self.execute(
            """
            INSERT INTO network_usage (
                timestamp, interface, operational_status, network_interface_type, kb_bytes_sent, kb_bytes_received
            )
            VALUES (%s, %s, %s, %s, %s, %s);
            """,
            (
                self.utcnow(),
                interface,
                operational_status,
                network_interface_type,
                kb_bytes_sent,
                kb_bytes_received,
            ),
        )

    def insert_ram_usage(self, total_kb: int, free_kb: int) -> None:
        self.execute(
            "INSERT INTO ram_usage (timestamp, total_kb, free_kb) VALUES (%s, %s, %s);",
            (self.utcnow(), total_kb, free_kb),
        )

    def insert_service_info(self, service_info: ServiceInfo) -> None:
        self.execute(
            """
            INSERT INTO services (timestamp, name, status, service_type, machine_name, process_ids)
            VALUES (%s, %s, %s, %s, %s, %s);
            """,
            (
                self.utcnow(),
                service_info.name,
                service_info.status,
                service_info.service_type,
                service_info.machine_name,
                ",".join(str(pid) for pid in service_info.process_ids),
            ),
        )
