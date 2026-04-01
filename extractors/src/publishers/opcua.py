"""
Publishers for all metrics to the OPC UA server

The publishers are responsible for writing the data to the OPC UA server.
"""

from lib.config import settings
from lib.opcua_client import OPCUAClient
from lib.models import CPUUsage, RAMUsage, NetworkUsage, ServiceInfo, KepEvent


async def publish_cpu_usage(client: OPCUAClient, cpu_usage: CPUUsage) -> None:
    data = cpu_usage.to_opcua(settings.timestamp_format)

    for field, value in data.items():
        node = client.get_node(f"{settings.metrics_config.cpu}.{field}")
        variant_type = await node.read_data_type_as_variant_type()
        await client.write_value(node, value, variant_type)


async def publish_ram_usage(client: OPCUAClient, ram_usage: RAMUsage) -> None:
    data = ram_usage.to_opcua(settings.timestamp_format)

    for field, value in data.items():
        node = client.get_node(f"{settings.metrics_config.ram}.{field}")
        variant_type = await node.read_data_type_as_variant_type()
        await client.write_value(node, value, variant_type)


async def publish_network_usage(
    client: OPCUAClient, network_usage: NetworkUsage
) -> None:
    data = network_usage.to_opcua(settings.timestamp_format)

    for field, value in data.items():
        node = client.get_node(f"{settings.metrics_config.network}.{field}")
        variant_type = await node.read_data_type_as_variant_type()
        await client.write_value(node, value, variant_type)


async def publish_service_info(client: OPCUAClient, service_info: ServiceInfo) -> None:
    data = service_info.to_opcua(settings.timestamp_format)

    for field, value in data.items():
        node = client.get_node(f"{settings.metrics_config.services}.{field}")
        variant_type = await node.read_data_type_as_variant_type()
        await client.write_value(node, value, variant_type)


async def publish_kep_event(client: OPCUAClient, kep_event: KepEvent) -> None:
    data = kep_event.to_opcua(settings.timestamp_format)

    for field, value in data.items():
        node = client.get_node(f"{settings.metrics_config.kepserverevents}.{field}")
        variant_type = await node.read_data_type_as_variant_type()
        await client.write_value(node, value, variant_type)
