"""
A data-change subscription on a set of nodes: the server pushes a value whenever one
changes, instead of the ingestor reading it on a timer.

One `NodeSubscription` serves one metric node or one tag channel. It only delivers:
`on_data` runs inside asyncua's notification handler, so it must be cheap and must
never raise (the ingestor just puts the value on a queue).
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from logging import getLogger

from asyncua import Node, ua

from lib.opcua_client import OPCUAClient
from lib.utils import utcnow

logger = getLogger(__name__)

# Monitored items are requested in chunks so a big channel stays under server limits.
ITEMS_PER_REQUEST = 1000

# Called with (key of the node, its data value, receive time).
OnData = Callable[[str, ua.DataValue, datetime], object]


@dataclass(frozen=True)
class SubscriptionConfig:
    sampling_interval_ms: int = 1000
    # Changes between two publishes are queued server side instead of overwritten.
    queue_size: int = 10
    publish_interval_ms: int = 500
    # No change for this long is logged once. It is not a reconnect reason: a quiet
    # plant is legitimate, the system heartbeat is what proves the connection.
    # None never logs it, for a node that is only written when something happens.
    stale_after_seconds: float | None = 60

    def for_publish_interval(self, seconds: float) -> "SubscriptionConfig":
        """
        Adapts the config to a source that publishes every `seconds`. Sampling at
        most twice as slow as the source keeps two writes from collapsing into one.
        """
        return replace(
            self,
            sampling_interval_ms=max(100, min(1000, int(seconds * 1000 / 2))),
            stale_after_seconds=(
                None
                if self.stale_after_seconds is None
                else max(self.stale_after_seconds, 5 * seconds)
            ),
        )


class NodeSubscription:
    def __init__(
        self,
        client: OPCUAClient,
        label: str,
        nodes: dict[str, str],
        config: SubscriptionConfig,
        on_data: OnData,
    ):
        """
        `nodes` maps the key passed to `on_data` (a metric or tag name) to the node id.
        """
        self.client = client
        self.label = label
        self.nodes = nodes
        self.config = config
        self.on_data = on_data

        self._keys: dict[str, str] = {}  # node id string -> key
        self._sub = None
        self._started_at: datetime | None = None
        self._last_received_at: datetime | None = None
        self._failed_status: ua.StatusCode | None = None
        self._was_stale = False

    async def start(self) -> None:
        self._sub = await self.client.create_subscription(
            self.config.publish_interval_ms, self
        )
        items: list[Node] = []
        for key, node_id in self.nodes.items():
            node = self.client.get_node(node_id)
            self._keys[node.nodeid.to_string()] = key
            items.append(node)

        rejected = 0
        for i in range(0, len(items), ITEMS_PER_REQUEST):
            chunk = items[i : i + ITEMS_PER_REQUEST]
            handles = await self._sub.subscribe_data_change(
                chunk,
                queuesize=self.config.queue_size,
                sampling_interval=self.config.sampling_interval_ms,
            )
            for node, handle in zip(chunk, handles):
                if isinstance(handle, ua.StatusCode):
                    rejected += 1
                    logger.warning(
                        f"{self.label} Could not subscribe to {node.nodeid.to_string()}: {handle.name}"
                    )
        if rejected == len(items):
            raise ConnectionError(
                f"{self.label} None of {len(items)} nodes could be subscribed"
            )
        self._started_at = utcnow()
        logger.info(
            f"{self.label} Subscribed to {len(items) - rejected}/{len(items)} nodes"
        )

    async def stop(self) -> None:
        if self._sub is not None:
            sub, self._sub = self._sub, None
            await sub.delete()

    async def datachange_notification(self, node: Node, val, data) -> None:
        now = utcnow()
        self._last_received_at = now
        key = self._keys.get(node.nodeid.to_string())
        if key is not None:
            self.on_data(key, data.monitored_item.Value, now)

    def status_change_notification(self, status: ua.StatusChangeNotification) -> None:
        logger.warning(
            f"{self.label} Subscription status changed: {status.Status.name}"
        )
        if not status.Status.is_good():
            self._failed_status = status.Status

    def check_health(self) -> str | None:
        """
        Raises ConnectionError if the server ended the subscription. Returns a
        message once each time the subscription goes silent for too long, which can
        also just mean that nothing changed, so it never forces a reconnect.
        """
        if self._failed_status is not None:
            raise ConnectionError(
                f"{self.label} Subscription failed: {self._failed_status.name}"
            )
        since = self._last_received_at or self._started_at
        if since is None or self.config.stale_after_seconds is None:
            return None
        silent_for = (utcnow() - since).total_seconds()
        stale = silent_for > self.config.stale_after_seconds
        message = None
        if stale and not self._was_stale:
            message = f"{self.label} No changes received for {silent_for:.0f}s"
        self._was_stale = stale
        return message
