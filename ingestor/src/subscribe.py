import asyncio
import logging
import time

from asyncua import ua
from lib.models import (
    CPUUsage,
    KepEvent,
    NetworkUsage,
    RAMUsage,
    ServiceInfo,
    StorageUsage,
)
from lib.opc_handlers import subscribe_batch, subscribe_scalar
from lib.opcua_client import OPCUAClient
from lib.tag_reader import read_individually, read_with_timeout
from lib.utils import TAG_QUARANTINE_RETRY_SECONDS

from src.db import IngestorDatabase

logger = logging.getLogger(__name__)

# (server, channel) -> {tag: monotonic time when it may be retried}
_quarantined: dict[tuple[str, str], dict[str, float]] = {}
# (server, channel) -> in-flight background retry of that channel's quarantined tags
_retrying: dict[tuple[str, str], asyncio.Task] = {}


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
    return await client.get_node(metrics.host_name.prefix).read_value()


async def subscribe_tag_channel(
    client: OPCUAClient,
    db: IngestorDatabase,
    metrics,
    *,
    server_name: str,
    channel: str,
    tags: list[str],
) -> None:
    label = f"[{server_name}][{channel.upper()}]"
    prefix = metrics.tag_channels[server_name][channel]
    quarantined = _quarantined.setdefault((server_name, channel), {})
    now = time.monotonic()
    active = [t for t in tags if t not in quarantined]
    retry = [t for t, retry_at in quarantined.items() if retry_at <= now]

    started = time.perf_counter()
    if active:
        try:
            tag_values, timestamp = await read_with_timeout(client, active, prefix)
        except (TimeoutError, ua.UaError) as e:
            logger.warning(
                f"{label} Batch read of {len(active)} tags failed "
                f"({type(e).__name__}), reading tags one by one"
            )
            tag_values, timestamp = await read_individually(
                client, active, prefix, quarantined, label
            )
        read_seconds = time.perf_counter() - started
        rows = db.process_tag_values(tag_values, timestamp)
        db.save_many(rows)
        logger.info(
            f"{label} Saved {len(rows)} values from {len(active)} tags "
            f"(read {read_seconds:.2f}s, total {time.perf_counter() - started:.2f}s)"
            + (f", {len(quarantined)} quarantined" if quarantined else "")
        )

    # Retry quarantined tags in the background so a still-dead tag (5s timeout)
    # never delays this channel's next cycle.
    key = (server_name, channel)
    if retry and key not in _retrying:
        task = asyncio.create_task(
            _retry_quarantined(client, db, prefix, retry, quarantined, label)
        )
        _retrying[key] = task
        task.add_done_callback(lambda _, key=key: _retrying.pop(key, None))


async def _retry_quarantined(
    client: OPCUAClient,
    db: IngestorDatabase,
    prefix: str,
    tags: list[str],
    quarantined: dict[str, float],
    label: str,
) -> None:
    async def retry_one(tag: str) -> None:
        try:
            tag_values, timestamp = await read_with_timeout(client, [tag], prefix)
        except (TimeoutError, ua.UaError):
            quarantined[tag] = time.monotonic() + TAG_QUARANTINE_RETRY_SECONDS
            return
        quarantined.pop(tag, None)
        db.save_many(db.process_tag_values(tag_values, timestamp))
        logger.info(f"{label} Tag {tag} recovered, back in the batch")

    try:
        await asyncio.gather(*(retry_one(t) for t in tags))
    except Exception:
        logger.exception(f"{label} Retry of quarantined tags failed")
