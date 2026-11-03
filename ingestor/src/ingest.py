"""
Between the OPC UA notifications and the database: a queue.

The data-change callbacks only enqueue (`put_nowait`), so nothing slow can delay the
next notification. A consumer task decodes what was queued and writes it in one batch
per tick. The write runs in a worker thread: asyncio is single threaded, so a
blocking database call would otherwise stall the callbacks too.

One `Ingest` lives per server and survives reconnects, so rows that were decoded but
not yet written when a session dropped are still written once the next one is up.
"""

import asyncio
import logging
from datetime import datetime

from asyncua import ua
from lib.metrics import METRICS
from lib.models import TagData

from src.db import IngestorDatabase

logger = logging.getLogger(__name__)

FLUSH_INTERVAL_SECONDS = 1
# Bounds that keep memory flat during a long database outage; the oldest data goes first.
QUEUE_MAX_ITEMS = 100_000
MAX_PENDING_ROWS_PER_TABLE = 500_000


class Ingest:
    def __init__(self, db: IngestorDatabase, label: str):
        self.db = db
        self.label = label
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX_ITEMS)
        self._dropped = 0
        # table -> rows decoded and waiting to be written
        self._pending: dict[str, list[dict[str, object]]] = {}
        self._last_timestamp: dict[str, datetime] = {}
        self._awaiting_first: set[str] = set()
        self._write_failing = False

    def new_session(self, metrics: list[str]) -> None:
        """
        A new subscription delivers each node's current value once. For a metric that
        value is usually the sample already stored, see `_add_metric`.
        """
        self._awaiting_first = set(metrics)

    # --- called from asyncua's notification handler: enqueue and nothing else ---

    def on_metric(self, name: str, data_value: ua.DataValue, received_at: datetime):
        self._put(("metric", name, data_value, received_at))

    def on_tag(self, tag: str, data_value: ua.DataValue, received_at: datetime):
        self._put(("tag", tag, data_value, received_at))

    def _put(self, item: tuple) -> None:
        if self._queue.full():
            self._queue.get_nowait()
            self._dropped += 1
        self._queue.put_nowait(item)

    # --- the consumer ---

    async def run(self) -> None:
        while True:
            await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
            await self.flush()

    async def flush(self) -> None:
        """
        Decodes everything queued and writes it. A failed write keeps the rows for the
        next tick and never raises: the OPC UA session has nothing to do with it.
        """
        self._decode_queued()
        if self._dropped:
            logger.warning(
                f"{self.label} Queue full, dropped the {self._dropped} oldest values"
            )
            self._dropped = 0
        if not self._pending:
            return

        batch, self._pending = self._pending, {}
        try:
            await asyncio.to_thread(self.db.insert_many, batch)
        except Exception:
            self._requeue(batch)
            if not self._write_failing:
                self._write_failing = True
                logger.exception(
                    f"{self.label} Database write failed, keeping the rows to retry"
                )
            return
        if self._write_failing:
            self._write_failing = False
            logger.info(f"{self.label} Database writes recovered")
        counts = ", ".join(f"{table} {len(rows)}" for table, rows in batch.items())
        logger.info(f"{self.label} Wrote rows: {counts}")

    def _requeue(self, batch: dict[str, list[dict[str, object]]]) -> None:
        for table, rows in batch.items():
            kept = rows + self._pending.get(table, [])
            if len(kept) > MAX_PENDING_ROWS_PER_TABLE:
                lost = len(kept) - MAX_PENDING_ROWS_PER_TABLE
                logger.warning(f"{self.label} Dropped {lost} oldest {table} rows")
                kept = kept[lost:]
            self._pending[table] = kept

    def _decode_queued(self) -> None:
        while True:
            try:
                kind, key, data_value, received_at = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                if kind == "metric":
                    self._add_metric(key, data_value)
                else:
                    self._add_tag(key, data_value, received_at)
            except Exception as e:
                logger.warning(f"{self.label} Dropped {kind} '{key}': {e}")

    def _add_metric(self, name: str, data_value: ua.DataValue) -> None:
        metric = METRICS[name]
        models = metric.decode(data_value)
        if not models:
            return

        newest = max(m.timestamp for m in models)
        last = self._last_timestamp.get(name)
        first = name in self._awaiting_first
        self._awaiting_first.discard(name)
        if first and not metric.idempotent and last is not None and newest <= last:
            return  # the value the server sends on subscribe, already stored

        self._last_timestamp[name] = newest if last is None else max(newest, last)
        rows = [
            {metric.columns.get(f, f): v for f, v in m.to_row().items()}
            for m in models
        ]
        self._pending.setdefault(metric.table_name, []).extend(rows)

    def _add_tag(self, tag: str, data_value: ua.DataValue, received_at: datetime):
        if data_value.Value is None:
            raise ValueError("no value")
        status = data_value.StatusCode
        row = TagData(
            tag=tag,
            value=str(data_value.Value.Value),
            status_code=status.name if status is not None else "Unknown",
            source_timestamp=data_value.SourceTimestamp,
            server_timestamp=data_value.ServerTimestamp,
            logger_timestamp=received_at,
        )
        self._pending.setdefault("tags", []).append(row.model_dump())
