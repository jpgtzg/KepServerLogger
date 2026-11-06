import asyncio
import time
from collections import deque
from collections.abc import Callable
from logging import getLogger

from asyncua import Node

from lib.models import HeartbeatRTT
from lib.opcua_client import OPCUAClient
from lib.utils import HEARTBEAT_INTERVAL_SECONDS, MAX_BUFFERED_RTTS, utcnow

logger = getLogger(__name__)


class SystemHeartbeatHandler:
    def __init__(
        self,
        client: OPCUAClient,
        max_heartbeat: int,
        echo: bool,
        receive_path: str,
        send_path: str,
        pair: str,
        max_rtt: float = 2.0,
        stale_after: float = 5.0,
        on_rtt: Callable[[HeartbeatRTT], None] | None = None,
    ):
        self.client = client
        self.pair = pair
        self.on_rtt = on_rtt
        self.max_heartbeat = max_heartbeat
        # The paths are named from the heartbeat owners's point of view, so the echoing
        # side listens on the ownser's send path and answers on its receive path.
        if echo:
            send_path, receive_path = receive_path, send_path
        self.send_path = send_path
        self.receive_path = receive_path
        self.max_rtt = max_rtt
        self.stale_after = stale_after

        self.echo = echo

        self._increasing = True
        self._heartbeat = 0

        self._sub = None

        self._last_received_value: int | None = None
        self._last_received_at = None

        self._sent_at_map: dict[int, float] = {}
        # Measured RTTs waiting to be published; the oldest are dropped when full.
        self._rtts: deque[HeartbeatRTT] = deque(maxlen=MAX_BUFFERED_RTTS)

        self.running_task = None

    async def start(
        self,
        on_stale: Callable[[], object] | None = None,
    ) -> None:
        self._sub = await self.client.create_subscription(500, self)
        node = self.client.get_node(self.receive_path)
        await self._sub.subscribe_data_change(node)

        if not self.echo:
            self.running_task = asyncio.create_task(
                self.run(HEARTBEAT_INTERVAL_SECONDS, on_stale=on_stale),
            )

    async def stop(self) -> None:
        # Stop the sender first: on a dead connection deleting the subscription
        # raises, and the task must not be left running into the next session.
        if self.running_task is not None:
            self.running_task.cancel()
            await asyncio.gather(self.running_task, return_exceptions=True)
            self.running_task = None
        sub, self._sub = self._sub, None
        if sub is not None:
            try:
                await sub.delete()
            except Exception:
                logger.warning(
                    "[SYSTEM-HEARTBEAT] Could not delete subscription", exc_info=True
                )

    async def datachange_notification(self, node: Node, val, data):
        if self.echo:
            await self.echo_value(val)
        else:
            now = utcnow()
            time_diff = now - self._last_received_at if self._last_received_at else None
            self._last_received_at = now

            if self._last_received_value is not None:
                delta = val - self._last_received_value
                if abs(delta) != 1:
                    logger.warning(
                        f"[SYSTEM-HEARTBEAT] Unexpected jump: {self._last_received_value} -> {val}"
                    )
            logger.info(
                "[SYSTEM-HEARTBEAT] Received value %s on %s (%.3fs since last beat)",
                val,
                self.receive_path,
                time_diff.total_seconds() if time_diff else -1,
            )

            self._last_received_value = val

            sent_at = self._sent_at_map.pop(val, None)
            if sent_at is not None:
                rtt = time.monotonic() - sent_at
                heartbeat_rtt = HeartbeatRTT(
                    timestamp=now,
                    pair=self.pair,
                    value=val,
                    rtt_ms=rtt * 1000,
                )
                self._rtts.append(heartbeat_rtt)
                if self.on_rtt is not None:
                    self.on_rtt(heartbeat_rtt)
                if rtt > self.max_rtt:
                    logger.warning(
                        f"[SYSTEM-HEARTBEAT] Slow echo on {self.receive_path}: value {val} took {rtt:.3f}s (max {self.max_rtt:.3f}s)",
                    )
                else:
                    logger.info("[SYSTEM-HEARTBEAT] RTT for value %s: %.3fs", val, rtt)
            else:
                logger.warning(
                    f"[SYSTEM-HEARTBEAT] Received value {val} on {self.receive_path} is not one we sent",
                )

    async def echo_value(self, val) -> None:
        node = self.client.get_node(self.send_path)
        variant_type = await node.read_data_type_as_variant_type()
        await self.client.write_value(node, val, variant_type)

    def drain_rtts(self) -> list[HeartbeatRTT]:
        """Returns the buffered RTTs, oldest first, and empties the buffer."""
        return [self._rtts.popleft() for _ in range(len(self._rtts))]

    def is_stale(self) -> bool:
        if self._last_received_at is None:
            return False
        elapsed = (utcnow() - self._last_received_at).total_seconds()
        return elapsed > self.stale_after

    async def send_heartbeat(
        self,
    ):
        self._update_heartbeat()
        self._sent_at_map[self._heartbeat] = time.monotonic()
        logger.info(f"[SYSTEM-HEARTBEAT] Publishing heartbeat value={self._heartbeat}")
        node = self.client.get_node(self.send_path)
        variant_type = await node.read_data_type_as_variant_type()
        await self.client.write_value(node, self._heartbeat, variant_type)

    def _update_heartbeat(self):
        if self._heartbeat == self.max_heartbeat and self._increasing:
            self._increasing = False
        elif self._heartbeat == 0 and not self._increasing:
            self._increasing = True

        self._heartbeat += 1 if self._increasing else -1

    async def run(
        self,
        interval: float,
        on_stale: Callable[[], object] | None = None,
    ) -> None:
        """
        Sends a heartbeat every `interval` seconds until cancelled, independent of
        the metric loop. `on_stale` is called on every beat while the echo is stale.
        """
        while True:
            try:
                await self.send_heartbeat()
            except Exception:
                logger.exception("[SYSTEM-HEARTBEAT] Failed to send heartbeat")

            if self.is_stale() and on_stale is not None:
                on_stale()

            await asyncio.sleep(interval)
