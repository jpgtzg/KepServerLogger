import logging
import os
import re
import traceback
from collections import deque
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.handlers import TimedRotatingFileHandler

from lib.models import AgentError
from lib.utils import (
    MAX_BUFFERED_ERRORS,
    MAX_ERROR_TRACEBACK_CHARS,
    MAX_ERRORS_PER_PUBLISH,
)

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


_COMPONENT_TAG = re.compile(r"^(?:\[[^\]]*\]\s*)*\[([^\]]+)\]")


class ErrorBufferHandler(logging.Handler):
    """
    Keeps the WARNING and ERROR records for the extractor to publish to the ingestor.
    It only appends, so publishing never logs more errors because of it, and the
    oldest records are dropped once the buffer is full.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self._errors: deque[AgentError] = deque(maxlen=MAX_BUFFERED_ERRORS)

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        tag = _COMPONENT_TAG.match(message)
        details = None
        if record.exc_info and record.exc_info[1] is not None:
            exc = record.exc_info[1]
            message = f"{message}: {type(exc).__name__}: {exc}"
            details = "".join(traceback.format_exception(*record.exc_info))
            details = details[-MAX_ERROR_TRACEBACK_CHARS:]
        self._errors.append(
            AgentError(
                timestamp=datetime.fromtimestamp(record.created, UTC),
                level=record.levelname,
                component=tag.group(1) if tag else record.name,
                message=message,
                traceback=details,
            )
        )

    def drain(self) -> list[AgentError]:
        """Returns up to one publish worth of errors, oldest first, and removes them."""
        count = min(len(self._errors), MAX_ERRORS_PER_PUBLISH)
        return [self._errors.popleft() for _ in range(count)]


def config_logging(log_dir: str = "logs", app_level: int = logging.INFO):
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

    console_handler = logging.StreamHandler()
    console_handler.setLevel(app_level)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
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
