import asyncio
import logging
import os
import time

from lib.logging import config_logging
from lib.monitor import OPCUAMonitor
from lib.opc_handlers import safe_handle
from lib.opcua_client import OPCUAClient
from lib.settings import MetricType
from lib.utils import OPCUA_REQUEST_TIMEOUT_SECONDS, RECONNECT_DELAY

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

    try:
        while True:
            await _run_session()
    except KeyboardInterrupt:
        logger.info("Stopping logger...")


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

    logger.info("Initialization complete, starting main loop...")
    await asyncio.sleep(5)

    start_time = time.time()
    try:
        async with client:
            logger.info("OPC UA client connected, starting main loop")
            monitor = OPCUAMonitor()
            while True:
                for metric_type, tag, function in PUBLISHERS:
                    if metric_type in settings.metrics_to_log:
                        await safe_handle(
                            tag,
                            monitor,
                            function(client, settings.metrics_config),
                        )

                await safe_handle(
                    "HOSTNAME",
                    monitor,
                    publish_hostname(client, settings.metrics_config),
                )

                await asyncio.sleep(settings.polling_interval_seconds)
    except ConnectionError as e:
        logger.warning(
            f"Connection lost ({type(e).__name__}: {e}), reconnecting in {RECONNECT_DELAY}s..."
        )
        await asyncio.sleep(RECONNECT_DELAY)
    finally:
        logger.info(f"Session uptime: {time.time() - start_time:.2f} seconds")


if __name__ == "__main__":
    if os.name != "nt":
        raise RuntimeError("This extractor currently targets Windows.")
    asyncio.run(main())
