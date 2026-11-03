import asyncio
import logging
import os
import time

from lib.heartbeat import SystemHeartbeatHandler
from lib.logging import config_logging
from lib.monitor import OPCUAMonitor
from lib.opc_handlers import safe_handle
from lib.opcua_client import OPCUAClient
from lib.settings import MetricType
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
    publish_cpu,
    publish_hostname,
    publish_kepserver_events,
    publish_network,
    publish_ram,
    publish_services,
    publish_storage,
)
from src.state import config, settings

config_logging()
logger = logging.getLogger(__name__)

PUBLISHERS = [
    (MetricType.CPU, "CPU", publish_cpu),
    (MetricType.RAM, "RAM", publish_ram),
    (MetricType.STORAGE, "STORAGE", publish_storage),
    (MetricType.NETWORK, "NETWORK", publish_network),
    (MetricType.SERVICES, "SERVICES", publish_services),
    (MetricType.KEPSERVER_EVENTS, "KEPSERVER_EVENTS", publish_kepserver_events),
]


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
            collector = SystemHeartbeatHandler(
                client=client,
                max_heartbeat=MAX_HEARTBEAT_NUMBER,
                echo=True,
                send_path=COLLECTOR_HEARTBEAT_SEND_PATH,
                receive_path=COLLECTOR_HEARTBEAT_RECEIVE_PATH,
                max_rtt=settings.polling_interval_seconds * 2,
                stale_after=settings.polling_interval_seconds * 5,
            )
            agent = SystemHeartbeatHandler(
                client=client,
                max_heartbeat=MAX_HEARTBEAT_NUMBER,
                echo=False,
                send_path=AGENT_HEARTBEAT_SEND_PATH,
                receive_path=AGENT_HEARTBEAT_RECEIVE_PATH,
                max_rtt=settings.polling_interval_seconds * 2,
                stale_after=settings.polling_interval_seconds * 5,
            )
            await collector.start()
            await agent.start(
                on_stale=lambda: logger.warning(
                    "[SYSTEM-HEARTBEAT] Agent heartbeat is stale"
                )
            )
            try:
                await _publish_forever(client)
            finally:
                await collector.stop()
                await agent.stop()
    finally:
        logger.info(f"Session uptime: {time.monotonic() - start_time:.2f} seconds")


async def _publish_forever(client: OPCUAClient) -> None:
    """
    Publishes every enabled metric and the hostname once per cycle, concurrently.
    A failing metric is logged and skipped; a ConnectionError, or the same metric
    failing too many cycles in a row, cancels the cycle and ends the session.
    """
    monitor = OPCUAMonitor()
    publishers = [
        (tag, publish)
        for metric_type, tag, publish in PUBLISHERS
        if metric_type in settings.metrics_to_log
    ] + [("HOSTNAME", publish_hostname)]

    while True:
        async with asyncio.TaskGroup() as tg:
            for tag, publish in publishers:
                tg.create_task(
                    safe_handle(tag, monitor, publish(client, settings.metrics_config))
                )
        await asyncio.sleep(settings.polling_interval_seconds)


if __name__ == "__main__":
    if os.name != "nt":
        raise RuntimeError("This extractor currently targets Windows.")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopping extractor...")
