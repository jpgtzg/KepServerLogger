import asyncio
import os
import time
from src.metrics.events import get_kepserver_events
import logging
from logging import getLogger

from lib.config import MetricType, config, settings
from lib.opcua_client import OPCUAClient


from src.metrics import (
    get_memory_info,
    get_network_interfaces,
    get_service_info,
    get_total_cpu_usage,
)
from src.publishers.opcua import (
    publish_cpu_usage,
    publish_kep_event,
    publish_network_usage,
    publish_ram_usage,
    publish_service_info,
)

logger = getLogger(__name__)


async def run_cycle(client: OPCUAClient) -> None:
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


async def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Keep our own code verbose; silence noisy third-party packages.
    for name in ("src", "lib", "__main__"):
        logging.getLogger(name).setLevel(logging.INFO)

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

    reconnect_delay = 10

    while True:
        try:
            async with client:
                logger.info("OPC UA connection established")
                while True:
                    try:
                        await run_cycle(client)
                    except asyncio.CancelledError as e:
                        logger.error(f"[MAIN] OPC UA request cancelled: {e}")
                    except ConnectionError:
                        raise
                    except Exception as e:
                        logger.error(f"[MAIN] cycle failed: {e}")
                    await asyncio.sleep(1)
        except ConnectionError as e:
            logger.warning(f"[MAIN] Connection lost: {e}. Reconnecting in {reconnect_delay}s...")
        except Exception as e:
            logger.error(f"[MAIN] Unexpected error: {e}. Reconnecting in {reconnect_delay}s...")
        await asyncio.sleep(reconnect_delay)


if __name__ == "__main__":
    # Match current implementation target (Windows-only service metrics).
    if os.name != "nt":
        raise RuntimeError("This extractor currently targets Windows.")
    asyncio.run(main())
