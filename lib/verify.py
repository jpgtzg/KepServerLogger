"""
Run this once to get a list of all nodes that need to be created in KepServer.
"""

from lib.config import settings, MetricType
from lib.mapping import (
    CPU_FIELDS,
    RAM_FIELDS,
    NETWORK_FIELDS,
    SERVICE_FIELDS,
)


def print_required_nodes() -> None:
    nodes = []

    if MetricType.CPU in settings.metrics_to_log:
        for field in CPU_FIELDS:
            nodes.append(f"{settings.metrics_config.cpu.prefix}.{field}")

    if MetricType.RAM in settings.metrics_to_log:
        for field in RAM_FIELDS:
            nodes.append(f"{settings.metrics_config.ram.prefix}.{field}")

    if MetricType.NETWORK in settings.metrics_to_log:
        for interface in settings.metrics_config.network.interfaces:
            for field in NETWORK_FIELDS:
                nodes.append(
                    f"{settings.metrics_config.network.prefix}.{interface}.{field}"
                )

    if MetricType.SERVICES in settings.metrics_to_log:
        for name in settings.metrics_config.services.names:
            for field in SERVICE_FIELDS:
                nodes.append(
                    f"{settings.metrics_config.services.prefix}.{name}.{field}"
                )

    if MetricType.KEPSERVER_EVENTS in settings.metrics_to_log:
        nodes.append(f"{settings.metrics_config.events.prefix}.batch")

    print(f"\n{len(nodes)} nodes need to be created in KepServer:\n")
    for node in nodes:
        print(f"  {node}")


if __name__ == "__main__":
    print_required_nodes()
