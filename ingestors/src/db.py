"""
Logger for ingesting data into the database.

Receives data from the OPC UA server and ingests it into the database.
"""

import os
import signal

from dotenv import load_dotenv
from lib.config import Config
from lib.constants import format_timestamp
from lib.database import ProjectDatabase

load_dotenv()

config = Config.load()


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

    def save_many(self, rows: list[tuple[str, str, str, str | None, str]]) -> None:
        if not rows:
            return
        with self.transaction():
            self.execute_many(
                """
                INSERT INTO tags (tag, value, status_code, source_timestamp, server_timestamp)
                VALUES (%s, %s, %s, %s, %s)
                """,
                rows,
            )


db = TagsDatabase()
db.initialize()


def save_many_to_db(tag_values, timestamp: str):
    rows = []
    for tag_name, data_value in tag_values:
        source_ts = format_timestamp(
            data_value.SourceTimestamp, config.timestamp_format
        )
        rows.append(
            (
                tag_name,
                str(data_value.Value.Value),
                data_value.StatusCode.name,
                source_ts,
                timestamp,
            )
        )

    if not rows:
        return

    db.save_many(rows)


def setup_exit_handler(loop):
    def exit_gracefully(*args):
        print("Exiting...")
        loop.stop()

    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)
