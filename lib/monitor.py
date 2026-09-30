from lib.utils import MAX_CONSECUTIVE_METRIC_FAILURES


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
