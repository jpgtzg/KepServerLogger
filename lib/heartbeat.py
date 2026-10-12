import time
from logging import getLogger

from asyncua import Node

from lib.models import Heartbeat
from lib.opc_handlers import publish_scalar
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
        self.send_path = send_path
        self.receive_path = receive_path
        self.max_rtt = max_rtt
        self.stale_after = stale_after

        self.echo = echo

        self._increasing = True
        self._heartbeat = Heartbeat(timestamp=utcnow(), value=0)

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
        self._sent_at_map[self._heartbeat.value] = time.monotonic()
        await publish_scalar(
            client=self.client,
            data=self._heartbeat,
            prefix=self.send_path,
            logging_str=f"[HEARTBEAT] Publishing heartbeat value: {self._heartbeat}",
        )

    def _update_heartbeat(self):
        self._heartbeat.timestamp = utcnow()
        if self._heartbeat.value == self.max_heartbeat and self._increasing:
            self._increasing = False
        elif self._heartbeat.value == 0 and not self._increasing:
            self._increasing = True

        self._heartbeat.value = (
            self._heartbeat.value + 1 if self._increasing else self._heartbeat.value - 1
        )
