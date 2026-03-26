from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

import psycopg

from models import KepEvent, ServiceInfo


class Database:
    def __init__(self) -> None:
        self._conn: psycopg.Connection | None = None
        self._retention_days = 7

    def initialize(self) -> None:
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        retention_days_str = os.getenv("LOG_RETENTION_DAYS", "7")

        if not db_name or not db_user or not db_password:
            raise RuntimeError("DB_NAME, DB_USER, and DB_PASSWORD must be set.")

        try:
            self._retention_days = int(retention_days_str)
        except ValueError:
            print(f"Invalid LOG_RETENTION_DAYS value '{retention_days_str}', defaulting to 7.")
            self._retention_days = 7

        conn_string = (
            f"host={db_host} port={db_port} dbname={db_name} user={db_user} password={db_password}"
        )
        self._conn = psycopg.connect(conn_string, autocommit=False)

        with self._conn.cursor() as cur:
            cur.execute(
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

                CREATE INDEX IF NOT EXISTS idx_cpu_timestamp       ON cpu_usage (timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_network_timestamp   ON network_usage (timestamp DESC, interface);
                CREATE INDEX IF NOT EXISTS idx_ram_timestamp       ON ram_usage (timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_services_timestamp  ON services (timestamp DESC, name);
                CREATE INDEX IF NOT EXISTS idx_events_timestamp    ON events (timestamp DESC);
                """
            )
            self._conn.commit()

        for table_name in ("cpu_usage", "network_usage", "ram_usage", "services", "events"):
            self._setup_table(table_name)

    def _setup_table(self, table_name: str) -> None:
        conn = self._require_conn()
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT create_hypertable('{table_name}', 'timestamp', if_not_exists => TRUE);"
            )
            cur.execute(
                f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM timescaledb_information.jobs
                        WHERE hypertable_name = '{table_name}'
                        AND proc_name = 'policy_retention'
                    ) THEN
                        PERFORM add_retention_policy('{table_name}', INTERVAL '{self._retention_days} days');
                    END IF;
                END $$;
                """
            )
            conn.commit()
        print(f"Table {table_name} configured with {self._retention_days} days retention.")

    @contextmanager
    def transaction(self) -> Iterator[None]:
        conn = self._require_conn()
        try:
            yield
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def insert_event(self, event: KepEvent) -> None:
        conn = self._require_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events (hash, timestamp, event_name, source, message)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (hash, timestamp) DO NOTHING;
                """,
                (
                    event.hash,
                    datetime.now(timezone.utc),
                    event.name,
                    event.source,
                    event.message,
                ),
            )

    def insert_cpu_usage(self, cpu_usage: float) -> None:
        conn = self._require_conn()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO cpu_usage (timestamp, usage) VALUES (%s, %s);",
                (datetime.now(timezone.utc), cpu_usage),
            )

    def insert_network_metrics(
        self,
        interface: str,
        operational_status: str,
        network_interface_type: str,
        kb_bytes_sent: float,
        kb_bytes_received: float,
    ) -> None:
        conn = self._require_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO network_usage (
                    timestamp, interface, operational_status, network_interface_type, kb_bytes_sent, kb_bytes_received
                )
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (
                    datetime.now(timezone.utc),
                    interface,
                    operational_status,
                    network_interface_type,
                    kb_bytes_sent,
                    kb_bytes_received,
                ),
            )

    def insert_ram_usage(self, total_kb: int, free_kb: int) -> None:
        conn = self._require_conn()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ram_usage (timestamp, total_kb, free_kb) VALUES (%s, %s, %s);",
                (datetime.now(timezone.utc), total_kb, free_kb),
            )

    def insert_service_info(self, service_info: ServiceInfo) -> None:
        conn = self._require_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO services (timestamp, name, status, service_type, machine_name, process_ids)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (
                    datetime.now(timezone.utc),
                    service_info.name,
                    service_info.status,
                    service_info.service_type,
                    service_info.machine_name,
                    ",".join(str(pid) for pid in service_info.process_ids),
                ),
            )

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _require_conn(self) -> psycopg.Connection:
        if self._conn is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._conn
