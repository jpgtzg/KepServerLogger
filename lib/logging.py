import logging
import os
import json
import math
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler

log_context: ContextVar[dict] = ContextVar("log_context", default={})

# Name of the server the current task is working for. Each asyncio task has its
# own copy, so concurrent per-server tasks don't overwrite each other.
current_server: ContextVar[str | None] = ContextVar("current_server", default=None)


class ServerPrefixFilter(logging.Filter):
    """Prefixes log messages with the server the current task belongs to."""

    def filter(self, record: logging.LogRecord) -> bool:
        server = current_server.get()
        if server:
            message = record.getMessage()
            prefix = f"[{server}]"
            if not message.startswith(prefix):
                record.msg = f"{prefix} {message}"
                record.args = None
        return True


def set_log_context(**fields):
    """Set only explicit, non-secret identifiers for the current async task."""
    log_context.set({**log_context.get(), **fields})


def _json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


class JsonFormatter(logging.Formatter):
    """One JSON object per physical line, including exception tracebacks."""

    def format(self, record):
        payload = {
            "schema_version": 1,
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "severity": record.levelname,
            "service": "idl-ingestor",
            "logger": record.name,
            "message": record.getMessage(),
            **log_context.get(),
        }
        for field in ("event", "data", "units"):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(_json_safe(payload), ensure_ascii=False, allow_nan=False)


def config_logging(log_dir: str = "logs", app_level: int = logging.INFO, *, json_console: bool = False):
    LOG_FILE = os.path.join(log_dir, "app.log")
    os.makedirs(log_dir, exist_ok=True)

    file_handler = TimedRotatingFileHandler(
        filename=LOG_FILE,
        when="midnight",  # Rotate at midnight each day
        interval=1,  # Every 1 day
        backupCount=7,  # Keep last 7 days of logs
        encoding="utf-8",
        utc=False,  # Use local time; set True for UTC
    )
    file_handler.suffix = "%Y-%m-%d.log"
    file_handler.setLevel(app_level)

    console_handler = logging.StreamHandler(sys.stdout if json_console else None)
    console_handler.setLevel(app_level)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(JsonFormatter() if json_console else formatter)
    for handler in (file_handler, console_handler):
        handler.addFilter(ServerPrefixFilter())

    logging.basicConfig(
        level=app_level,
        handlers=[file_handler, console_handler],
    )

    for name in ("src", "lib", "__main__"):
        logging.getLogger(name).setLevel(app_level)

    # asyncua logs protocol internals (including raw certificate bytes) at INFO,
    # which drowns out real warnings/errors and can render as unreadable binary
    # garbage in the log file. WARNING+ from asyncua is still real signal (e.g.
    # "Future for request id ... is already done" on a timed-out request).
    logging.getLogger("asyncua").setLevel(logging.WARNING)
