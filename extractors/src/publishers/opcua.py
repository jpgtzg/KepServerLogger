"""
Publishers for all metrics to the OPC UA server

The publishers are responsible for writing the data to the OPC UA server.
"""

import json
from asyncua import ua
from lib.config import settings
from lib.opcua_client import OPCUAClient
from lib.models import CPUUsage, RAMUsage, NetworkUsage, ServiceInfo, KepEvent
from logging import getLogger

logger = getLogger(__name__)

# TODO: Use the node names from the verify module


async def publish_cpu_usage(client: OPCUAClient, cpu_usage: CPUUsage) -> None:
    logger.info(f"[CPU] Publishing CPU usage: {cpu_usage}")
    data = cpu_usage.to_opcua(settings.timestamp_format)

    for field, value in data.items():
        node = client.get_node(f"{settings.metrics_config.cpu.prefix}.{field}")
        variant_type = await node.read_data_type_as_variant_type()
        await client.write_value(node, value, variant_type)


async def publish_ram_usage(client: OPCUAClient, ram_usage: RAMUsage) -> None:
    logger.info(f"[RAM] Publishing RAM usage: {ram_usage}")
    data = ram_usage.to_opcua(settings.timestamp_format)

    for field, value in data.items():
        node = client.get_node(f"{settings.metrics_config.ram.prefix}.{field}")
        variant_type = await node.read_data_type_as_variant_type()
        await client.write_value(node, value, variant_type)


async def publish_service_info(
    client: OPCUAClient, service_info: list[ServiceInfo]
) -> None:
    logger.info(f"[SERVICES] Publishing {len(service_info)} service(s): {[s.name for s in service_info[:3]]}...")
    for service in service_info:
        data = service.to_opcua(settings.timestamp_format)
        service_key = service.name.replace('.', '_')
        for index, (field, value) in enumerate(data.items()):
            node = client.get_node(
                f"{settings.metrics_config.services.prefix}.{service_key}_{index}"
            )
            variant_type = await node.read_data_type_as_variant_type()
            await client.write_value(node, value, variant_type)


async def publish_network_usage(
    client: OPCUAClient, network_usage: list[NetworkUsage]
) -> None:
    logger.info(f"[NETWORK] Publishing {len(network_usage)} interface(s)")
    data = [iface.to_opcua(settings.timestamp_format) for iface in network_usage]
    node = client.get_node(f"{settings.metrics_config.network.prefix}.batch")
    await client.write_value(node, json.dumps(data), ua.VariantType.String)


async def publish_kep_event(client: OPCUAClient, kep_events: list[KepEvent]) -> None:
    logger.info(f"[EVENTS] Publishing {len(kep_events)} event(s): {[e.name for e in kep_events[:3]]}...")
    if not kep_events:
        return
    data = [kep_event.to_opcua(settings.timestamp_format) for kep_event in kep_events]
    node = client.get_node(f"{settings.metrics_config.kepserverevents.prefix}.batch")
    await client.write_value(node, json.dumps(data), ua.VariantType.String)
