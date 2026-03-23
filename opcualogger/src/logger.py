from pathlib import Path
from asyncua import ua
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import signal
import psycopg2
import psycopg2.extras
import os

load_dotenv()

# ---------------- Configuration ----------------
LOG_DIR = Path(os.getenv("LOG_DIR", "/app/logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "5432")
DB_NAME     = os.getenv("DB_NAME")
DB_USER     = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

RETENTION_DAYS   = int(os.getenv("LOG_RETENTION_DAYS"))
CLEANUP_INTERVAL = int(os.getenv("LOG_CLEANUP_INTERVAL"))

TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

def format_timestamp(ts):
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts.strftime(TIMESTAMP_FORMAT)
    try:
        return ts.isoformat()
    except AttributeError:
        return str(ts)


def _init_db():
    print(f"Connecting to TimescaleDB at {DB_HOST}:{DB_PORT}/{DB_NAME}...")
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            server_timestamp    TIMESTAMPTZ NOT NULL,
            tag                 TEXT NOT NULL,
            value               TEXT,
            status_code         TEXT,
            source_timestamp    TIMESTAMPTZ
        );
    """)

    # Convert to hypertable (safe to call repeatedly)
    cur.execute("""
        SELECT create_hypertable('tags', 'server_timestamp', if_not_exists => TRUE);
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_tags_tag_timestamp ON tags (tag, server_timestamp DESC);")

    cur.close()
    conn.autocommit = False
    print("Database initialized.")
    return conn


conn = _init_db()

def save_many_to_db(tag_values, timestamp: str):
    rows = []
    for tag_name, data_value in tag_values:
        # Handling the conversion to string/format as you did before
        source_ts = format_timestamp(data_value.SourceTimestamp)
        rows.append((
            tag_name,
            str(data_value.Value.Value), # Ensure value is a string for the TEXT column
            data_value.StatusCode.name,
            source_ts,
            timestamp,
        ))

    if not rows:
        return

    # Use a context manager for the connection to handle commits/rollbacks
    # AND a context manager for the cursor to handle closing it
    with conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(
                cur,  # <--- PASS THE CURSOR HERE, NOT CONN
                """
                INSERT INTO tags (tag, value, status_code, source_timestamp, server_timestamp)
                VALUES (%s, %s, %s, %s, %s)
                """,
                rows,
                page_size=100 # Optional: improves performance for large batches
            )


# Retention is handled by TimescaleDB policy — this is kept for compatibility
def delete_older_than_retention():
    print("Retention is managed by TimescaleDB policy.")
    return 0

async def periodic_cleanup(interval=CLEANUP_INTERVAL):
    import asyncio
    while True:
        await asyncio.sleep(interval)
        print("Retention is managed by TimescaleDB — no manual cleanup needed.")


def setup_exit_handler(loop):
    def exit_gracefully(*args):
        print("Exiting...")
        loop.stop()
    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)