import logging
import os
from logging.handlers import TimedRotatingFileHandler


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
