"""
Publishing of the local metrics to the OPC UA server.

`GETTERS` maps each metric name to the function that gathers its models. To add a
metric, add a getter in `src/metrics`, a line here, and its `Metric` in `lib/metrics.py`.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from asyncua import ua
from lib.metrics import Metric
from lib.models import OPCUAModel
from lib.opcua_client import OPCUAClient
from lib.settings import ExtractorSettings

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

# Every getter returns a list of models, so a scalar metric is a list of one.
Getter = Callable[[ExtractorSettings], Awaitable[list[OPCUAModel]]]


def _one(getter: Callable[[], OPCUAModel]) -> Getter:
    async def get(settings: ExtractorSettings) -> list[OPCUAModel]:
        return [await asyncio.to_thread(getter)]

    return get


def _many(getter: Callable[[], list]) -> Getter:
    async def get(settings: ExtractorSettings) -> list[OPCUAModel]:
        return await asyncio.to_thread(getter)

    return get


async def _services(settings: ExtractorSettings) -> list[OPCUAModel]:
    if not settings.services:
        logger.warning("[SERVICES] No service names configured, nothing to publish")
    return list(
        await asyncio.gather(
            *(asyncio.to_thread(get_service_info, name) for name in settings.services)
        )
    )


GETTERS: dict[str, Getter] = {
    "cpu": _one(get_total_cpu_usage),
    "ram": _one(get_memory_info),
    "storage": _one(get_storage),
    "network": _many(get_network_interfaces),
    "services": _services,
    "events": _many(get_kepserver_events),
}


async def publish_metric(
    client: OPCUAClient, metric: Metric, settings: ExtractorSettings
) -> None:
    models = await GETTERS[metric.name](settings)
    if not models:
        return
    node = client.get_node(metric.node_id(settings.node_prefix))
    await client.write_value(node, metric.encode(models), ua.VariantType.String)
    logger.info(f"[{metric.name.upper()}] Published {len(models)} item(s)")


async def publish_hostname(client: OPCUAClient, settings: ExtractorSettings) -> None:
    hostname = get_hostname()
    logger.info(f"[HOSTNAME] Publishing hostname: {hostname}")
    node = client.get_node(settings.host_name_node)
    variant_type = await node.read_data_type_as_variant_type()
    await client.write_value(node, hostname, variant_type)
