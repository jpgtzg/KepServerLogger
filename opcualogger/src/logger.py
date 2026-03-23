from pathlib import Path
from asyncua import ua
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import signal
import psycopg2
import psycopg2.extras
import os

load_dotenv()

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

    cur.execute("""
        SELECT create_hypertable('tags', 'server_timestamp', if_not_exists => TRUE);
    """)

    cur.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM timescaledb_information.jobs 
                WHERE hypertable_name = 'tags' 
                AND proc_name = 'policy_retention'
            ) THEN
                PERFORM add_retention_policy('tags', INTERVAL '{RETENTION_DAYS} days');
            END IF;
        END $$;
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_tags_tag_timestamp ON tags (tag, server_timestamp DESC);")

    cur.close()
    conn.autocommit = False
    print(f"Database initialized with {RETENTION_DAYS} days retention policy.")
    return conn

conn = _init_db()

def save_many_to_db(tag_values, timestamp: str):
    rows = []
    for tag_name, data_value in tag_values:
        source_ts = format_timestamp(data_value.SourceTimestamp)
        rows.append((
            tag_name,
            str(data_value.Value.Value),
            data_value.StatusCode.name,
            source_ts,
            timestamp,
        ))

    if not rows:
        return

    with conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(
                cur, 
                """
                INSERT INTO tags (tag, value, status_code, source_timestamp, server_timestamp)
                VALUES (%s, %s, %s, %s, %s)
                """,
                rows,
                page_size=100
            )

def setup_exit_handler(loop):
    def exit_gracefully(*args):
        print("Exiting...")
        loop.stop()
    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)