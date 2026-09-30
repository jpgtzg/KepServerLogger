import logging

from lib.models import (
    CPUUsage,
    Hostname,
    KepEvent,
    NetworkUsage,
    RAMUsage,
    ServiceInfo,
    StorageUsage,
)
from lib.opc_handlers import subscribe_batch, subscribe_scalar
from lib.opcua_client import OPCUAClient

from src.db import IngestorDatabase

logger = logging.getLogger(__name__)


async def subscribe_cpu(client: OPCUAClient, db: IngestorDatabase, metrics) -> None:
    cpu_usage = await subscribe_scalar(client, metrics.cpu.prefix, CPUUsage)
    db.insert_cpu_usage(cpu_usage)
    logger.info("[CPU] Logged CPU usage")


async def subscribe_ram(client: OPCUAClient, db: IngestorDatabase, metrics) -> None:
    ram_usage = await subscribe_scalar(client, metrics.ram.prefix, RAMUsage)
    db.insert_ram_usage(ram_usage)
    logger.info("[RAM] Logged RAM usage")


async def subscribe_storage(client: OPCUAClient, db: IngestorDatabase, metrics) -> None:
    storage_usage = await subscribe_scalar(client, metrics.storage.prefix, StorageUsage)
    db.insert_storage_usage(storage_usage=storage_usage)
    logger.info("[STORAGE] Logged STORAGE usage")


async def subscribe_network(client: OPCUAClient, db: IngestorDatabase, metrics) -> None:
    interfaces = await subscribe_batch(client, metrics.network.prefix, NetworkUsage)
    for interface in interfaces:
        db.insert_network_metrics(interface)
    logger.info(f"[NETWORK] Logged {len(interfaces)} interfaces")


async def subscribe_services(
    client: OPCUAClient, db: IngestorDatabase, metrics
) -> None:
    services = await subscribe_batch(client, metrics.services.prefix, ServiceInfo)
    for service in services:
        db.insert_service_info(service)
    logger.info(f"[SERVICES] Logged {len(services)} services")


async def subscribe_kepserver_events(
    client: OPCUAClient, db: IngestorDatabase, metrics
) -> None:
    events = await subscribe_batch(client, metrics.kepserverevents.prefix, KepEvent)
    for event in events:
        db.insert_event(event)
    logger.info(f"[EVENTS] Logged {len(events)} KepServer events")


async def subscribe_hostname(client: OPCUAClient, metrics) -> str:
    hostname = await subscribe_scalar(client, metrics.host_name.prefix, Hostname)
    return hostname.host_name


async def subscribe_tag_channels(
    client: OPCUAClient,
    db: IngestorDatabase,
    metrics,
    *,
    server_name: str,
    channel_tags: dict,
) -> None:
    channel_prefixes = metrics.tag_channels[server_name]
    for channel, tags in channel_tags.items():
        if not tags:
            logger.info(
                f"[{server_name}][{channel.upper()}] No tags found for this channel, skipping."
            )
            continue
        tag_values, timestamp = await client.read_batch(
            tags=tags, prefix=channel_prefixes[channel]
        )
        rows = db.process_tag_values(tag_values, timestamp)
        db.save_many(rows)
        logger.info(
            f"[{server_name}][{channel.upper()}] Saved {len(rows)} values from {len(tags)} tags"
        )
