from collections.abc import Awaitable, Callable
from logging import getLogger

from lib.utils import MAX_CONSECUTIVE_METRIC_FAILURES

logger = getLogger(__name__)


class OPCUAMonitor:
    """
    A class to monitor the number of consecutive failures for each process done on a OPCUA connection.
    """

    def __init__(self):
        self.consecutive_failures: dict[str, int] = {}

    def on_success(self, component: str) -> None:
        self.consecutive_failures.pop(component, None)

    def on_failure(self, component: str) -> None:
        count = self.consecutive_failures.get(component, 0) + 1
        self.consecutive_failures[component] = count
        if count >= MAX_CONSECUTIVE_METRIC_FAILURES:
            raise ConnectionError(
                f"{component} failed {count} times in a row, forcing reconnect"
            )


async def safe_handle(
    metric: str,
    monitor: OPCUAMonitor,
    coro: Awaitable[object],
    on_error_hook: Callable[[Exception], object] | None = None,
) -> None:
    """
    Awaits one unit of work. A failure is logged and counted by the monitor instead
    of stopping the caller; a ConnectionError always propagates so the session reconnects.
    """
    try:
        await coro
        monitor.on_success(metric)
    except ConnectionError:
        raise
    except Exception as e:
        logger.exception(f"[{metric}] failed")
        if on_error_hook is not None:
            on_error_hook(e)
        monitor.on_failure(metric)
