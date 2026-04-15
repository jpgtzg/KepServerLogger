import asyncio
import logging
import os
import time

from lib.config import MetricType, config, settings
from lib.logging import config_logging
from lib.opcua_client import OPCUAClient

from src.metrics import (
    get_memory_info,
    get_network_interfaces,
    get_service_info,
    get_total_cpu_usage,
)
from src.metrics.events import get_kepserver_events
from src.publishers.opcua import (
    publish_cpu_usage,
    publish_kep_event,
    publish_network_usage,
    publish_ram_usage,
    publish_service_info,
)

config_logging()
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Starting metrics extractor...")
    logger.info(f"Connecting to {config.kepserver_server_url}...")

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

    logger.info("Initialization complete, starting main loop...")
    time.sleep(5)

    async with client:
        logger.info("OPC UA client connected, starting main loop")
        start_time = time.time()
        try:
            while True:
                if MetricType.CPU in settings.metrics_to_log:
                    try:
                        await publish_cpu_usage(client, get_total_cpu_usage())
                    except ConnectionError:
                        raise
                    except Exception:
                        logger.exception("[CPU] publish failed")

                if MetricType.RAM in settings.metrics_to_log:
                    try:
                        await publish_ram_usage(client, get_memory_info())
                    except ConnectionError:
                        raise
                    except Exception:
                        logger.exception("[RAM] publish failed")

                if MetricType.SERVICES in settings.metrics_to_log:
                    try:
                        service_info = [
                            get_service_info(service_name)
                            for service_name in settings.metrics_config.services.names
                        ]
                        await publish_service_info(client, service_info)
                    except ConnectionError:
                        raise
                    except Exception:
                        logger.exception("[SERVICES] publish failed")

                if MetricType.NETWORK in settings.metrics_to_log:
                    try:
                        await publish_network_usage(client, get_network_interfaces())
                    except ConnectionError:
                        raise
                    except Exception:
                        logger.exception("[NETWORK] publish failed")

                if MetricType.KEPSERVER_EVENTS in settings.metrics_to_log:
                    try:
                        await publish_kep_event(client, get_kepserver_events())
                    except ConnectionError:
                        raise
                    except Exception:
                        logger.exception("[EVENTS] publish failed")
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping logger...")
        finally:
            await client.disconnect()
            logger.info("OPC UA client disconnected, exiting main loop")
            logger.info(f"Total uptime: {time.time() - start_time:.2f} seconds")


if __name__ == "__main__":
    # Match current implementation target (Windows-only service metrics).
    if os.name != "nt":
        raise RuntimeError("This extractor currently targets Windows.")
    asyncio.run(main())
