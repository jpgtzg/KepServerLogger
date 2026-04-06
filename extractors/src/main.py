import asyncio
import os
import time
from src.metrics.events import get_kepserver_events
from src.metrics import (
    get_memory_info,
    get_network_interfaces,
    get_total_cpu_usage,
    get_service_info,
)

from lib.config import config, settings, MetricType
from lib.opcua_client import OPCUAClient
from src.publishers.opcua import (
    publish_cpu_usage,
    publish_ram_usage,
    publish_service_info,
    publish_network_usage,
    publish_kep_event,
)
from logging import getLogger

logger = getLogger(__name__)


async def run_cycle(client: OPCUAClient) -> None:
    if MetricType.CPU in settings.metrics_to_log:
        try:
            await publish_cpu_usage(client, get_total_cpu_usage())
        except Exception as e:
            logger.error(f"[CPU] publish failed: {e}")

    if MetricType.RAM in settings.metrics_to_log:
        try:
            await publish_ram_usage(client, get_memory_info())
        except Exception as e:
            logger.error(f"[RAM] publish failed: {e}")

    if MetricType.SERVICES in settings.metrics_to_log:
        try:
            service_info = [
                get_service_info(service_name)
                for service_name in settings.metrics_config.services.names
            ]
            await publish_service_info(client, service_info)
        except Exception as e:
            logger.error(f"[SERVICES] publish failed: {e}")

    if MetricType.NETWORK in settings.metrics_to_log:
        try:
            await publish_network_usage(client, get_network_interfaces())
        except Exception as e:
            logger.error(f"[NETWORK] publish failed: {e}")

    if MetricType.KEPSERVER_EVENTS in settings.metrics_to_log:
        try:
            await publish_kep_event(client, get_kepserver_events())
        except Exception as e:
            logger.error(f"[EVENTS] publish failed: {e}")


async def main() -> None:

    client = OPCUAClient(
        url=config.kepserver_server_url,
        app_uri=config.app_uri,
        name=config.application_name,
        cert_path=config.cert_path,
        key_path=config.key_path,
        username=config.kepserver_username,
        password=config.kepserver_password,
    )

    await client.setup()

    logger.info("Extractor initialized")
    time.sleep(5)

    async with client:
        while True:
            try:
                await run_cycle(client)
            except Exception as e:
                logger.error(f"[MAIN] cycle failed: {e}")
            await asyncio.sleep(1)


if __name__ == "__main__":
    # Match current implementation target (Windows-only service metrics).
    if os.name != "nt":
        raise RuntimeError("This extractor currently targets Windows.")
    asyncio.run(main())
