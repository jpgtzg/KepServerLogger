"""
Run this once to get a list of all nodes that need to be created in KepServer.
"""

from lib.config import config, settings, MetricType
from lib.models import CPUUsage, RAMUsage, NetworkUsage, ServiceInfo, KepEvent
from lib.tag_extractor import extract_tags_from_csv


def get_cpu_node_names() -> list[str]:
    return [
        f"{settings.metrics_config.cpu.prefix}.{field}"
        for field in CPUUsage.model_fields.keys()
    ]


def get_ram_node_names() -> list[str]:
    return [
        f"{settings.metrics_config.ram.prefix}.{field}"
        for field in RAMUsage.model_fields.keys()
    ]


def get_network_node_names() -> list[str]:
    return [
        f"{settings.metrics_config.network.prefix}.{interface}.{field}"
        for interface in settings.metrics_config.network.interfaces
        for field in NetworkUsage.model_fields.keys()
    ]


def get_services_node_names() -> list[str]:
    return [
        f"{settings.metrics_config.services.prefix}.{name.replace('.', '_')}_{index}"
        for name in settings.metrics_config.services.names
        for index, _ in enumerate(ServiceInfo.model_fields.keys())
    ]


def get_kepserver_events_node_names() -> list[str]:
    return [f"{settings.metrics_config.kepserverevents.prefix}.batch"]


def get_plc_tags() -> list[str]:
    return extract_tags_from_csv(
        prefix=settings.metrics_config.plc_tags.prefix,
        separator=config.csv_tag_separator,
        exclude_tags=["_Write", "_WRITE"],
        tag_column=config.csv_tag_column_name,
        filename=config.csv_filename,
    )


def print_required_nodes() -> None:
    nodes = []

    if MetricType.CPU in settings.metrics_to_log:
        nodes.extend(get_cpu_node_names())

    if MetricType.RAM in settings.metrics_to_log:
        nodes.extend(get_ram_node_names())

    # if MetricType.NETWORK in settings.metrics_to_log:
    #     for interface in settings.metrics_config.network.interfaces:
    #         for field in NetworkUsage.model_fields.keys():
    #             nodes.append(
    #                 f"{settings.metrics_config.network.prefix}.{interface}.{field}"
    #             )

    if MetricType.SERVICES in settings.metrics_to_log:
        nodes.extend(get_services_node_names())

    if MetricType.KEPSERVER_EVENTS in settings.metrics_to_log:
        nodes.extend(get_kepserver_events_node_names())

    print(f"\n{len(nodes)} nodes need to be created in KepServer:\n")
    for node in nodes:
        print(f"  {node}")


if __name__ == "__main__":
    print_required_nodes()
