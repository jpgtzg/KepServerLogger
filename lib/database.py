from __future__ import annotations

import re
from contextlib import contextmanager
from logging import getLogger
from typing import Iterable, Iterator, LiteralString, Sequence

import psycopg
from psycopg.sql import SQL, Identifier, Literal

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_logger = getLogger(__name__)


class ProjectDatabase:
    def __init__(
        self,
        *,
        host: str,
        port: int | str,
        db_name: str,
        user: str,
        password: str,
        retention_days: int,
    ) -> None:
        self._host = host
        self._port = str(port)
        self._db_name = db_name
        self._user = user
        self._password = password
        self._retention_days = retention_days
        self._conn: psycopg.Connection | None = None

    def ensure_database_exists(self) -> None:
        """
        Creates self._db_name on the server if it doesn't already exist.
        Connects to the maintenance "postgres" database to do so, since a
        database can't be created from within a connection to itself and
        CREATE DATABASE can't run inside a transaction block.
        """
        self._validate_identifier(self._db_name)
        conn_string = (
            f"host={self._host} port={self._port} dbname=postgres"
            f" user={self._user} password={self._password}"
        )
        with psycopg.connect(conn_string, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (self._db_name,)
                )
                if cur.fetchone() is None:
                    _logger.info(f"Database '{self._db_name}' does not exist, creating it...")
                    cur.execute(
                        SQL("CREATE DATABASE {}").format(Identifier(self._db_name))
                    )

    def connect(self) -> None:
        conn_string = (
            f"host={self._host} port={self._port} dbname={self._db_name}"
            f" user={self._user} password={self._password}"
        )
        self._conn = psycopg.connect(conn_string, autocommit=False)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @contextmanager
    def transaction(self) -> Iterator[None]:
        conn = self.connection
        try:
            yield
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    @property
    def connection(self) -> psycopg.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn

    @property
    def retention_days(self) -> int:
        return self._retention_days

    def initialize_schema(
        self,
        *,
        create_statements: Sequence[LiteralString],
        indexes: Sequence[LiteralString] = (),
        hypertables: Sequence[tuple[str, str]] = (),
    ) -> None:
        conn = self.connection
        with conn.cursor() as cur:
            for statement in create_statements:
                cur.execute(statement)
            for index_statement in indexes:
                cur.execute(index_statement)
        conn.commit()

        for table_name, timestamp_column in hypertables:
            self.ensure_hypertable_and_retention(table_name, timestamp_column)

    def ensure_hypertable_and_retention(
        self, table_name: str, timestamp_column: str
    ) -> None:
        self._validate_identifier(table_name)
        self._validate_identifier(timestamp_column)
        conn = self.connection

        with conn.cursor() as cur:
            cur.execute(
                SQL("SELECT create_hypertable({}, {}, if_not_exists => TRUE);").format(
                    Literal(table_name),
                    Literal(timestamp_column),
                )
            )
            cur.execute(
                SQL(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM timescaledb_information.jobs
                            WHERE hypertable_name = {}
                              AND proc_name = 'policy_retention'
                        ) THEN
                            PERFORM add_retention_policy({}, INTERVAL '{} days');
                        END IF;
                    END $$;
                """
                ).format(
                    Literal(table_name),
                    Literal(table_name),
                    Literal(self._retention_days),
                )
            )
        conn.commit()

    def execute(
        self, query: LiteralString, params: Sequence[object] | None = None
    ) -> None:
        with self.connection.cursor() as cur:
            cur.execute(query, params)

    def execute_many(
        self, query: LiteralString, rows: Iterable[Sequence[object]]
    ) -> None:
        with self.connection.cursor() as cur:
            cur.executemany(query, rows)

    @staticmethod
    def _validate_identifier(identifier: str) -> None:
        if not _IDENTIFIER_RE.match(identifier):
            raise ValueError(f"Unsafe SQL identifier: {identifier}")

