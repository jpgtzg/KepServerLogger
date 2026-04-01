"""
Subscribers for all metrics from the OPC UA server.
The subscribers are responsible for reading the data from the OPC UA server.
"""

import json
from lib.config import settings
from lib.opcua_client import OPCUAClient
from lib.models import CPUUsage, RAMUsage, NetworkUsage, ServiceInfo, KepEvent
from lib.mapping import CPU_FIELDS, RAM_FIELDS, NETWORK_FIELDS, SERVICE_FIELDS


async def subscribe_cpu_usage(client: OPCUAClient) -> CPUUsage:
    data = {}
    for field in CPU_FIELDS:
        node = client.get_node(f"{settings.metrics_config.cpu.prefix}.{field}")
        data[field] = await node.read_value()
    return CPUUsage(**data)


async def subscribe_ram_usage(client: OPCUAClient) -> RAMUsage:
    data = {}
    for field in RAM_FIELDS:
        node = client.get_node(f"{settings.metrics_config.ram.prefix}.{field}")
        data[field] = await node.read_value()
    return RAMUsage(**data)


async def subscribe_network_usage(client: OPCUAClient) -> list[NetworkUsage]:
    results = []
    for interface in settings.metrics_config.network.interfaces:
        data = {"interface": interface}
        for field in NETWORK_FIELDS:
            node = client.get_node(
                f"{settings.metrics_config.network.prefix}.{interface}.{field}"
            )
            data[field] = await node.read_value()
        results.append(NetworkUsage(**data))
    return results


async def subscribe_service_info(client: OPCUAClient) -> list[ServiceInfo]:
    results = []
    for name in settings.metrics_config.services.names:
        data = {}
        for field in SERVICE_FIELDS:
            node = client.get_node(
                f"{settings.metrics_config.services.prefix}.{name}.{field}"
            )
            data[field] = await node.read_value()
        # process_ids was serialized as "1,2,3" — deserialize back to list[int]
        raw_pids = data.get("process_ids", "")
        data["process_ids"] = [int(pid) for pid in raw_pids.split(",") if pid]
        results.append(ServiceInfo(**data))
    return results


async def subscribe_kep_events(client: OPCUAClient) -> list[KepEvent]:
    node = client.get_node(f"{settings.metrics_config.events.prefix}.batch")
    raw: str = await node.read_value()
    if not raw:
        return []
    return [KepEvent(**e) for e in json.loads(raw)]
