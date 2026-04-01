"""
Publishers for all metrics to the OPC UA server
"""

from lib.config import settings
from lib.opcua_client import OPCUAClient
from lib.models import CPUUsage


async def publish_cpu_usage(client: OPCUAClient, cpu_usage: CPUUsage) -> None:
    data = cpu_usage.to_opcua(settings.timestamp_format)

    for field, value in data.items():
        node = client.get_node(f"{settings.metrics_config.cpu}.{field}")
        variant_type = await node.read_data_type_as_variant_type()
        await client.write_value(node, value, variant_type)
