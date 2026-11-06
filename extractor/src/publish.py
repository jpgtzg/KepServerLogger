"""
Publishing of the local metrics to the OPC UA server.

`_GETTERS` maps each metric name to the function that gathers its models. To add a
metric, add a getter in `src/metrics`, a line here, and its `Metric` in `lib/metrics.py`.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence

from asyncua import ua
from lib.heartbeat import SystemHeartbeatHandler
from lib.logging import ErrorBufferHandler
from lib.metrics import Metric
from lib.models import OPCUAModel
from lib.opcua_client import OPCUAClient
from lib.settings import ExtractorSettings

from src.metrics import (
    get_hostname,
    get_kepserver_events,
    get_memory_info,
    get_network_interfaces,
    get_services,
    get_storage,
    get_total_cpu_usage,
)

logger = logging.getLogger(__name__)

# Every getter returns a list of models, so a scalar metric is a list of one.
MetricGetterModel = Callable[[ExtractorSettings], Awaitable[list[OPCUAModel]]]


def as_async_getter(
    getter: Callable[..., OPCUAModel | Sequence[OPCUAModel]],
    args: Callable[[ExtractorSettings], tuple] = lambda settings: (),
) -> MetricGetterModel:
    """
    Adapt a blocking getter into an async Getter.

    Runs the getter in a worker thread so it doesn't block the event loop,
    and normalizes a single model into a one-item list. `args` picks the
    getter's arguments out of the settings, for getters that need them.
    """

    async def get(settings: ExtractorSettings) -> list[OPCUAModel]:
        result = await asyncio.to_thread(getter, *args(settings))
        return [result] if isinstance(result, OPCUAModel) else list(result)

    return get


# Process-wide, unlike the heartbeat's: errors logged while disconnected must survive
# the reconnect so they can be published afterwards.
error_buffer = ErrorBufferHandler()

_GETTERS: dict[str, MetricGetterModel] = {
    "cpu": as_async_getter(get_total_cpu_usage),
    "ram": as_async_getter(get_memory_info),
    "storage": as_async_getter(get_storage),
    "network": as_async_getter(get_network_interfaces),
    "services": as_async_getter(get_services, lambda settings: (settings.services,)),
    "events": as_async_getter(get_kepserver_events),
    "errors": as_async_getter(error_buffer.drain),
}


def make_getters(heartbeat: SystemHeartbeatHandler) -> dict[str, MetricGetterModel]:
    """The getters for one session; the heartbeat one drains `heartbeat`'s RTTs."""
    return {**_GETTERS, "heartbeat": as_async_getter(heartbeat.drain_rtts)}


### < ----------- Actual publisher functions ----------- > ###


async def publish_metric(
    client: OPCUAClient,
    metric: Metric,
    settings: ExtractorSettings,
    getters: dict[str, MetricGetterModel],
) -> None:
    models = await getters[metric.name](settings)
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
