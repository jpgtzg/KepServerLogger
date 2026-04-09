"""
Subscribers for all metrics from the OPC UA server.
The subscribers are responsible for reading the data from the OPC UA server.
"""

import json

from lib.config import settings
from lib.models import CPUUsage, KepEvent, NetworkUsage, RAMUsage, ServiceInfo
from lib.opcua_client import OPCUAClient


async def subscribe_cpu_usage(client: OPCUAClient) -> CPUUsage:
    data = {}
    for field in CPUUsage.model_fields.keys():
        node = client.get_node(f"{settings.metrics_config.cpu.prefix}.{field}")
        data[field] = await node.read_value()
    return CPUUsage(**data)


async def subscribe_ram_usage(client: OPCUAClient) -> RAMUsage:
    data = {}
    for field in RAMUsage.model_fields.keys():
        node = client.get_node(f"{settings.metrics_config.ram.prefix}.{field}")
        data[field] = await node.read_value()
    return RAMUsage(**data)


async def subscribe_network_usage(client: OPCUAClient) -> list[NetworkUsage]:
    node = client.get_node(f"{settings.metrics_config.network.prefix}.batch")
    raw: str = await node.read_value()
    if not raw:
        return []
    return [NetworkUsage(**iface) for iface in json.loads(raw)]


async def subscribe_service_info(client: OPCUAClient) -> list[ServiceInfo]:
    results = []
    for name in settings.metrics_config.services.names:
        data = {}
        service_key = name.replace(".", "_")
        for index, field in enumerate(ServiceInfo.model_fields.keys()):
            node = client.get_node(
                f"{settings.metrics_config.services.prefix}.{service_key}_{index}"
            )
            data[field] = await node.read_value()
        # process_ids was serialized as "1,2,3" — deserialize back to list[int]
        raw_pids = data.get("process_ids", "")
        data["process_ids"] = [int(pid) for pid in raw_pids.split(",") if pid]
        results.append(ServiceInfo(**data))
    return results


async def subscribe_kep_events(client: OPCUAClient) -> list[KepEvent]:
    """
    "batch" is a special node that contains all the events in a single message.
    """

    node = client.get_node(f"{settings.metrics_config.kepserverevents.prefix}.batch")
    raw: str = await node.read_value()
    if not raw:
        return []
    return [KepEvent(**e) for e in json.loads(raw)]
