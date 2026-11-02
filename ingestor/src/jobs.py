"""
Collector jobs: what the ingestor polls for a server and how each job is scheduled.

Every tag channel and every metric is its own job running in its own task, so a
slow or failing read in one never delays the others.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from lib.monitor import OPCUAMonitor
from lib.opc_handlers import safe_handle
from lib.opcua_client import OPCUAClient
from lib.servers import ServerConfig
from lib.settings import MetricType

from src.db import IngestorDatabase
from src.state import settings
from src.subscribe import (
    subscribe_cpu,
    subscribe_kepserver_events,
    subscribe_network,
    subscribe_ram,
    subscribe_services,
    subscribe_storage,
    subscribe_tag_channel,
)

logger = logging.getLogger(__name__)

# A job is a name plus a factory that builds its coroutine for a given client.
Job = tuple[str, Callable[[OPCUAClient], Awaitable[None]]]

METRIC_COLLECTORS = [
    (MetricType.CPU, "CPU", subscribe_cpu),
    (MetricType.RAM, "RAM", subscribe_ram),
    (MetricType.STORAGE, "STORAGE", subscribe_storage),
    (MetricType.NETWORK, "NETWORK", subscribe_network),
    (MetricType.SERVICES, "SERVICES", subscribe_services),
    (MetricType.KEPSERVER_EVENTS, "KEPSERVER_EVENTS", subscribe_kepserver_events),
]


def build_jobs(
    server: ServerConfig, db: IngestorDatabase, channel_tags: dict[str, list[str]]
) -> list[Job]:
    """
    Builds the jobs for a server. Tag channels come first: they are the most
    important data. `channel_tags` is empty when tag channels are not logged.
    """
    jobs: list[Job] = []

    for channel, tags in channel_tags.items():
        if not tags:
            logger.info(
                f"[{server.name}][{channel.upper()}] No tags found for this channel, skipping."
            )
            continue
        jobs.append(
            (
                f"TAG_CHANNELS:{channel}",
                lambda client, channel=channel, tags=tags: subscribe_tag_channel(
                    client,
                    db,
                    settings.metrics_config,
                    server_name=server.name,
                    channel=channel,
                    tags=tags,
                ),
            )
        )

    for metric_type, name, collect in METRIC_COLLECTORS:
        if metric_type in settings.metrics_to_log:
            jobs.append(
                (
                    name,
                    lambda client, collect=collect: collect(
                        client, db, settings.metrics_config
                    ),
                )
            )

    return jobs


async def run_jobs(
    jobs: list[Job],
    client: OPCUAClient,
    monitor: OPCUAMonitor,
    db: IngestorDatabase,
    server_name: str,
) -> None:
    """
    Runs all jobs concurrently until one raises. TaskGroup cancels the rest and
    re-raises (e.g. the monitor's ConnectionError), which triggers a reconnect.
    """
    async with asyncio.TaskGroup() as tg:
        for name, make in jobs:
            tg.create_task(
                _run_periodic(
                    name,
                    settings.polling_interval_seconds,
                    monitor,
                    db,
                    lambda make=make: make(client),
                    server_name,
                )
            )


async def _run_periodic(
    name: str,
    interval: float,
    monitor: OPCUAMonitor,
    db: IngestorDatabase,
    make_coro: Callable[[], Awaitable[None]],
    server_name: str,
) -> None:
    """
    Runs one job forever at a fixed rate. A run that overruns the interval is not
    overlapped or "caught up": the next run starts right after it ends.
    """
    loop = asyncio.get_running_loop()
    next_run = loop.time()
    while True:
        await safe_handle(
            name,
            monitor,
            make_coro(),
            on_error_hook=lambda e: db.log_event("WARNING", name, e),
        )
        next_run += interval
        delay = next_run - loop.time()
        if delay < 0:
            logger.warning(
                f"[{server_name}] [{name}] Overran its {interval}s interval by {-delay:.2f}s"
            )
            next_run = loop.time()
            delay = 0
        await asyncio.sleep(delay)
