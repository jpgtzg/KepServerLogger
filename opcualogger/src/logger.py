from pathlib import Path
from asyncua import ua
from datetime import datetime, timedelta
from dotenv import load_dotenv
import signal
import sqlite3
import os

load_dotenv()
# ---------------- Configuration ----------------
# Base directory for logs (can be overridden with LOG_DIR env var)
LOG_DIR = Path(os.getenv("LOG_DIR", "/app/logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = LOG_DIR / os.getenv("DB_NAME")
RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS"))
CLEANUP_INTERVAL = int(os.getenv("LOG_CLEANUP_INTERVAL"))

TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

def format_timestamp(ts):
    """Return a nicely formatted timestamp string."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts.strftime(TIMESTAMP_FORMAT)
    try:
        return ts.isoformat()
    except AttributeError:
        return str(ts)


def _init_db():
    """Create SQLite database and logs table if needed."""
    print(f"Initializing database at {DB_PATH} (cwd={Path.cwd()})...")
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
    except sqlite3.OperationalError as e:
        print(f"SQLite OperationalError while opening database at {DB_PATH}: {e}")
        print("Check that the directory exists and that the container/user has write permissions (including SELinux and volume options).")
        raise

    conn.execute("PRAGMA journal_mode=WAL;")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag TEXT NOT NULL,
            value TEXT,
            status_code TEXT,
            source_timestamp TEXT,
            server_timestamp TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_logs_server_timestamp ON Tags(server_timestamp)"
    )
    conn.commit()
    return conn


conn = _init_db()


def save_to_db(tag_name: str, data_value: ua.DataValue, timestamp: str):
    """Insert a single log entry into SQLite."""
    source_ts = format_timestamp(data_value.SourceTimestamp)
    with conn:
        conn.execute(
            """
            INSERT INTO Tags (tag, value, status_code, source_timestamp, server_timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                tag_name,
                data_value.Value.Value,
                data_value.StatusCode.name,
                source_ts,
                timestamp,
            ),
        )


def save_many_to_db(tag_values, timestamp: str):
    """Insert many log entries into SQLite within a single transaction.

    tag_values is an iterable of (tag_name, data_value) pairs.
    """
    rows = []
    for tag_name, data_value in tag_values:
        source_ts = format_timestamp(data_value.SourceTimestamp)
        rows.append(
            (
                tag_name,
                data_value.Value.Value,
                data_value.StatusCode.name,
                source_ts,
                timestamp,
            )
        )

    if not rows:
        return

    with conn:
        conn.executemany(
            """
            INSERT INTO Tags (tag, value, status_code, source_timestamp, server_timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )


def delete_older_than_retention():
    """Delete log rows older than RETENTION_DAYS (based on server_timestamp)."""
    cutoff = (datetime.now() - timedelta(days=RETENTION_DAYS)).strftime(TIMESTAMP_FORMAT)
    with conn:
        cursor = conn.execute(
            "DELETE FROM Tags WHERE server_timestamp < ?", (cutoff,)
        )
        return cursor.rowcount


async def periodic_cleanup(interval=CLEANUP_INTERVAL):
    """Periodically delete log entries older than RETENTION_DAYS."""
    import asyncio

    while True:
        await asyncio.sleep(interval)
        deleted = delete_older_than_retention()
        if deleted:
            print(f"Retention cleanup: removed {deleted} rows older than {RETENTION_DAYS} days.")


# ---------------- Shutdown Handler ----------------
def setup_exit_handler(loop):
    """Stop the event loop on SIGINT/SIGTERM."""

    def exit_gracefully(*args):
        print("Exiting...")
        loop.stop()

    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)
