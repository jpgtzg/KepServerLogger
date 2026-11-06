import asyncio
import logging
import os
import time

from lib.heartbeat import SystemHeartbeatHandler
from lib.logging import config_logging
from lib.metrics import METRICS
from lib.monitor import OPCUAMonitor, safe_handle
from lib.opcua_client import OPCUAClient
from lib.utils import (
    AGENT_HEARTBEAT_RECEIVE_PATH,
    AGENT_HEARTBEAT_SEND_PATH,
    COLLECTOR_HEARTBEAT_RECEIVE_PATH,
    COLLECTOR_HEARTBEAT_SEND_PATH,
    MAX_HEARTBEAT_NUMBER,
    OPCUA_REQUEST_TIMEOUT_SECONDS,
    RECONNECT_DELAY,
)

from src.publish import (
    MetricGetterModel,
    error_buffer,
    make_getters,
    publish_hostname,
    publish_metric,
)
from src.state import config, settings

config_logging()
logging.getLogger().addHandler(error_buffer)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Starting metrics extractor...")
    while True:
        try:
            await _run_session()
        except Exception as e:
            reasons = e.exceptions if isinstance(e, BaseExceptionGroup) else (e,)
            logger.warning(
                "Session ended ("
                + "; ".join(f"{type(r).__name__}: {r}" for r in reasons)
                + f"), reconnecting in {RECONNECT_DELAY}s...",
                exc_info=not all(isinstance(r, ConnectionError) for r in reasons),
            )
        await asyncio.sleep(RECONNECT_DELAY)


async def _run_session() -> None:
    logger.info(f"Connecting to {config.kepserver_server_url}...")
    client = OPCUAClient(
        url=config.kepserver_server_url,
        app_uri=config.app_uri,
        name=config.application_name,
        cert_path=config.cert_path,
        key_path=config.key_path,
        username=config.kepserver_username,
        password=config.kepserver_password,
        timeout=OPCUA_REQUEST_TIMEOUT_SECONDS,
    )
    await client.setup()

    start_time = time.monotonic()
    try:
        async with client:
            logger.info("OPC UA client connected, starting main loop")
            collector_heartbeat = SystemHeartbeatHandler(
                client=client,
                max_heartbeat=MAX_HEARTBEAT_NUMBER,
                echo=True,
                send_path=COLLECTOR_HEARTBEAT_SEND_PATH,
                pair="collector",
                receive_path=COLLECTOR_HEARTBEAT_RECEIVE_PATH,
                max_rtt=settings.polling_interval_seconds * 2,
                stale_after=settings.polling_interval_seconds * 5,
            )
            agent_heartbeat = SystemHeartbeatHandler(
                client=client,
                max_heartbeat=MAX_HEARTBEAT_NUMBER,
                echo=False,
                send_path=AGENT_HEARTBEAT_SEND_PATH,
                pair="agent",
                receive_path=AGENT_HEARTBEAT_RECEIVE_PATH,
                max_rtt=settings.polling_interval_seconds * 2,
                stale_after=settings.polling_interval_seconds * 5,
            )
            try:
                await collector_heartbeat.start()
                await agent_heartbeat.start(
                    on_stale=lambda: logger.warning(
                        "[SYSTEM-HEARTBEAT] Agent heartbeat is stale"
                    )
                )
                await _publish_forever(client, make_getters(agent_heartbeat))
            finally:
                await collector_heartbeat.stop()
                await agent_heartbeat.stop()
    finally:
        logger.info(f"Session uptime: {time.monotonic() - start_time:.2f} seconds")


async def _publish_forever(
    client: OPCUAClient, getters: dict[str, MetricGetterModel]
) -> None:
    """
    Publishes every enabled metric and the hostname once per cycle, concurrently.
    A failing metric is logged and skipped; a ConnectionError, or the same metric
    failing too many cycles in a row, cancels the cycle and ends the session.
    """
    monitor = OPCUAMonitor()
    enabled = [METRICS[name] for name in settings.metrics]

    while True:
        async with asyncio.TaskGroup() as tg:
            for metric in enabled:
                tg.create_task(
                    safe_handle(
                        metric.name.upper(),
                        monitor,
                        publish_metric(client, metric, settings, getters),
                    )
                )
            tg.create_task(
                safe_handle("HOSTNAME", monitor, publish_hostname(client, settings))
            )
        await asyncio.sleep(settings.polling_interval_seconds)


if __name__ == "__main__":
    if os.name != "nt":
        raise RuntimeError("This extractor currently targets Windows.")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopping extractor...")
