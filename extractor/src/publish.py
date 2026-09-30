"""

Publishing functions for various metrics.

When adding new metrics, add a new function here and update the PUBLISHERS list in main.py.
"""

import logging

from lib.opc_handlers import publish_batch, publish_scalar
from lib.opcua_client import OPCUAClient

from src.metrics import (
    get_hostname,
    get_kepserver_events,
    get_memory_info,
    get_network_interfaces,
    get_service_info,
    get_storage,
    get_total_cpu_usage,
)

logger = logging.getLogger(__name__)


async def publish_cpu(client: OPCUAClient, metrics) -> None:
    data = get_total_cpu_usage()
    await publish_scalar(
        client,
        data,
        metrics.cpu.prefix,
        f"[CPU] Publishing CPU usage: {data}",
    )


async def publish_ram(client: OPCUAClient, metrics) -> None:
    data = get_memory_info()
    await publish_scalar(
        client,
        data,
        metrics.ram.prefix,
        f"[RAM] Publishing RAM usage: {data}",
    )


async def publish_storage(client: OPCUAClient, metrics) -> None:
    data = get_storage()
    await publish_scalar(
        client,
        data,
        metrics.storage.prefix,
        f"[STORAGE] Publishing STORAGE usage: {data}",
    )


async def publish_services(client: OPCUAClient, metrics) -> None:
    if not metrics.services or not metrics.services.names:
        logger.warning(
            "[SERVICES] No service names configured, skipping service info publishing"
        )
        return

    service_info = [get_service_info(name) for name in metrics.services.names]
    await publish_batch(
        client,
        service_info,
        metrics.services.prefix,
        f"[SERVICES] Publishing {len(service_info)} service(s): {[s.name for s in service_info[:3]]}...",
    )


async def publish_network(client: OPCUAClient, metrics) -> None:
    interfaces = get_network_interfaces()
    await publish_batch(
        client,
        interfaces,
        metrics.network.prefix,
        f"[NETWORK] Publishing {len(interfaces)} interface(s)",
    )


async def publish_kepserver_events(client: OPCUAClient, metrics) -> None:
    events = get_kepserver_events()
    if events:
        await publish_batch(
            client,
            events,
            metrics.kepserverevents.prefix,
            f"[EVENTS] Publishing {len(events)} event(s): {[e.name for e in events[:3]]}...",
        )


async def publish_hostname(client: OPCUAClient, metrics) -> None:
    hostname = get_hostname()
    await publish_scalar(
        client,
        hostname,
        metrics.host_name.prefix,
        f"[HOSTNAME] Publishing hostname: {hostname}",
    )
