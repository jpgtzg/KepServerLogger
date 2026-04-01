import asyncio
import os
from metrics.events import get_kepserver_events
from metrics import (
    get_memory_info,
    get_network_interfaces,
    get_total_cpu_usage,
    get_service_info,
)

from lib.config import config, settings, MetricType
from lib.opcua_client import OPCUAClient
from publishers.opcua import publish_cpu_usage
from publishers.opcua import publish_ram_usage
from publishers.opcua import publish_service_info
from publishers.opcua import publish_network_usage
from publishers.opcua import publish_kep_event


async def run_cycle(client: OPCUAClient) -> None:
    if MetricType.CPU in settings.metrics_to_log:
        cpu_usage = get_total_cpu_usage()
        await publish_cpu_usage(client, cpu_usage)

    if MetricType.RAM in settings.metrics_to_log:
        ram_usage = get_memory_info()
        await publish_ram_usage(client, ram_usage)

    if MetricType.SERVICES in settings.metrics_to_log:
        service_info = [
            get_service_info(service_name) for service_name in settings.service_names
        ]
        await publish_service_info(client, service_info)

    if MetricType.NETWORK in settings.metrics_to_log:
        network_interfaces = get_network_interfaces()
        await publish_network_usage(client, network_interfaces)

    if MetricType.KEPSERVER_EVENTS in settings.metrics_to_log:
        kep_events = get_kepserver_events()
        await publish_kep_event(client, kep_events)


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

    async with client:
        while True:
            await run_cycle(client)
            await asyncio.sleep(1)


if __name__ == "__main__":
    # Match current implementation target (Windows-only service metrics).
    if os.name != "nt":
        raise RuntimeError("This extractor currently targets Windows.")
    asyncio.run(main())
