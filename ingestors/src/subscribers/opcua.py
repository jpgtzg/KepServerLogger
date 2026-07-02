"""
Subscribers for all metrics from the OPC UA server.
The subscribers are responsible for reading the data from the OPC UA server.
"""

import json

from lib.models import (
    CPUUsage,
    KepEvent,
    NetworkUsage,
    OpcConnectionEvent,
    RAMUsage,
    ServiceInfo,
)
from lib.opcua_client import OPCUAClient
from lib.settings import MetricsConfig


async def subscribe_cpu_usage(client: OPCUAClient, metrics_config: MetricsConfig) -> CPUUsage:
    data = {}
    for field in CPUUsage.model_fields.keys():
        node = client.get_node(f"{metrics_config.cpu.prefix}.{field}")
        data[field] = await node.read_value()
    return CPUUsage(**data)


async def subscribe_ram_usage(client: OPCUAClient, metrics_config: MetricsConfig) -> RAMUsage:
    data = {}
    for field in RAMUsage.model_fields.keys():
        node = client.get_node(f"{metrics_config.ram.prefix}.{field}")
        data[field] = await node.read_value()
    return RAMUsage(**data)


async def subscribe_network_usage(client: OPCUAClient, metrics_config: MetricsConfig) -> list[NetworkUsage]:
    node = client.get_node(f"{metrics_config.network.prefix}.batch")
    raw: str = await node.read_value()
    if not raw:
        return []
    return [NetworkUsage(**iface) for iface in json.loads(raw)]


async def subscribe_service_info(client: OPCUAClient, metrics_config: MetricsConfig) -> list[ServiceInfo]:
    node = client.get_node(f"{metrics_config.services.prefix}.batch")
    raw: str = await node.read_value()
    if not raw:
        return []
    return [ServiceInfo(**s) for s in json.loads(raw)]


async def subscribe_kep_events(client: OPCUAClient, metrics_config: MetricsConfig) -> list[KepEvent]:
    """
    "batch" is a special node that contains all the events in a single message.
    """

    node = client.get_node(f"{metrics_config.kepserverevents.prefix}.batch")
    raw: str = await node.read_value()
    if not raw:
        return []
    return [KepEvent(**e) for e in json.loads(raw)]


async def subscribe_opc_connection_events(
    client: OPCUAClient,
    metrics_config: MetricsConfig,
) -> list[OpcConnectionEvent]:
    node = client.get_node(f"{metrics_config.opcdiagnostics.prefix}.batch")
    raw: str = await node.read_value()
    if not raw:
        return []
    return [OpcConnectionEvent(**e) for e in json.loads(raw)]
