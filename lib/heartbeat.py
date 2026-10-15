import asyncio
import time
from collections.abc import Callable
from logging import getLogger

from asyncua import Node

from lib.opcua_client import OPCUAClient
from lib.utils import utcnow

logger = getLogger(__name__)


class HeartbeatHandler:
    def __init__(
        self,
        client: OPCUAClient,
        max_heartbeat: int,
        echo: bool,
        receive_path: str,
        send_path: str,
        max_rtt: float = 2.0,
        stale_after: float = 5.0,
    ):
        self.client = client
        self.max_heartbeat = max_heartbeat
        # The paths are named from the collector's point of view, so the echoing
        # side listens on the collector's send path and answers on its receive path.
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

    async def start(self) -> None:
        self._sub = await self.client.create_subscription(500, self)
        node = self.client.get_node(self.receive_path)
        await self._sub.subscribe_data_change(node)

    async def stop(self) -> None:
        if self._sub is not None:
            await self._sub.delete()
            self._sub = None

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
                        f"[HEARTBEAT] Unexpected jump: {self._last_received_value} -> {val}"
                    )
            logger.info(
                "[HEARTBEAT] Received value %s on (%.3fs since last beat)",
                val,
                time_diff.total_seconds() if time_diff else -1,
            )

            self._last_received_value = val

            sent_at = self._sent_at_map.pop(val, None)
            if sent_at is not None:
                rtt = time.monotonic() - sent_at
                if rtt > self.max_rtt:
                    logger.warning(
                        f"[HEARTBEAT] Slow echo on {self.receive_path}: value {val} took {rtt:.3f}s (max {self.max_rtt:.3f}s)",
                    )
                else:
                    logger.info("[HEARTBEAT] RTT for value %s: %.3fs", val, rtt)
            else:
                logger.warning(
                    f"[HEARTBEAT] Received value {val} on {self.receive_path} is not one we sent",
                )

    async def echo_value(self, val) -> None:
        node = self.client.get_node(self.send_path)
        variant_type = await node.read_data_type_as_variant_type()
        await self.client.write_value(node, val, variant_type)

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
        logger.info(f"[HEARTBEAT] Publishing heartbeat value={self._heartbeat}")
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
        the metric loop. `on_stale` is called once each time the echo goes stale.
        """
        was_stale = False
        while True:
            try:
                await self.send_heartbeat()
            except Exception:
                logger.exception("[HEARTBEAT] Failed to send heartbeat")

            stale = self.is_stale()
            if stale and not was_stale and on_stale is not None:
                on_stale()
            was_stale = stale

            await asyncio.sleep(interval)
