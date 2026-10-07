"""
Ingestor for retrieving data from the OPC UA server and ingesting it into the database.
"""

import asyncio
import logging
from functools import partial

from lib.logging import config_logging
from lib.monitor import OPCUAMonitor
from lib.opc_handlers import safe_handle
from lib.opcua_client import OPCUAClient
from lib.servers import ServerConfig, load_servers_configs
from lib.settings import MetricType
from lib.utils import (
    OPCUA_REQUEST_TIMEOUT_SECONDS,
    RECONNECT_DELAY,
    get_channel_tags,
    get_server_channels,
)

from src.db import IngestorDatabase
from src.state import config, settings
from src.subscribe import (
    subscribe_cpu,
    subscribe_hostname,
    subscribe_kepserver_events,
    subscribe_network,
    subscribe_ram,
    subscribe_services,
    subscribe_storage,
    subscribe_tag_channels,
)

config_logging()
logger = logging.getLogger(__name__)

COLLECTORS = [
    (MetricType.CPU, "CPU", subscribe_cpu),
    (MetricType.RAM, "RAM", subscribe_ram),
    (MetricType.STORAGE, "STORAGE", subscribe_storage),
    (MetricType.NETWORK, "NETWORK", subscribe_network),
    (MetricType.SERVICES, "SERVICES", subscribe_services),
    (MetricType.KEPSERVER_EVENTS, "KEPSERVER_EVENTS", subscribe_kepserver_events),
]


async def main(server: ServerConfig):
    logger.info(f"[{server.name}] Initiating IDL Central Collector...")

    server_channels_config = get_server_channels(server, settings.metrics_config)
    channel_tags = get_channel_tags(server, settings)

    collectors = list(COLLECTORS)

    if server_channels_config is not None:
        collectors.insert(
            0,
            (
                MetricType.TAG_CHANNELS,
                "TAG_CHANNELS",
                partial(
                    subscribe_tag_channels,
                    server_name=server.name,
                    channel_tags=channel_tags,
                ),
            ),
        )

    db = IngestorDatabase(
        host=config.db_host,
        port=config.db_port,
        db_name=server.db_name,
        user=config.db_user,
        password=config.db_password,
        retention_days=settings.log_retention_days,
    )
    db.initialize()

    retry_count = 0
    while True:
        try:
            logger.info(f"[{server.name}] Connecting to {server.url}...")
            client = OPCUAClient(
                url=server.url,
                app_uri=config.app_uri,
                name=config.application_name,
                cert_path=server.cert_path,
                key_path=server.key_path,
                username=server.username,
                password=server.password,
                timeout=OPCUA_REQUEST_TIMEOUT_SECONDS,
            )
            await client.setup()

            async with client:
                host_name = await subscribe_hostname(client, settings.metrics_config)
                db.log_status("active", host_name=host_name)
                logger.info(f"[{server.name}] Connected — host: {host_name}")
                retry_count = 0

                monitor = OPCUAMonitor()
                while True:
                    for metric_type, metric, function in collectors:
                        if metric_type in settings.metrics_to_log:
                            await safe_handle(
                                metric,
                                monitor,
                                function(client, db, settings.metrics_config),
                                on_error_hook=lambda e, metric=metric: db.log_event(
                                    "WARNING", metric, e
                                ),
                            )

                    await asyncio.sleep(settings.polling_interval_seconds)

        except (KeyboardInterrupt, asyncio.CancelledError):
            db.log_status("inactive", reason="shutdown")
            logger.info(f"[{server.name}] Shutting down.")
            raise

        except Exception as e:
            error_id = db.log_event("ERROR", "RECONNECT", e)
            db.log_status("inactive", error_id=error_id)
            logger.exception(
                f"[{server.name}] Connection lost: {type(e).__name__}: {e}. "
                f"Retrying in {RECONNECT_DELAY}s... (attempt {retry_count + 1})",
            )
            retry_count += 1
            await asyncio.sleep(RECONNECT_DELAY)


async def run_all(servers: list) -> None:
    results = await asyncio.gather(*[main(s) for s in servers], return_exceptions=True)
    for server, result in zip(servers, results):
        if isinstance(result, Exception):
            logger.error(
                f"[{server.name}] Stopped unexpectedly: {result}", exc_info=result
            )


if __name__ == "__main__":
    servers = load_servers_configs()
    if MetricType.TAG_CHANNELS in settings.metrics_to_log:
        tag_channels_config = settings.metrics_config.tag_channels or {}
        missing = [s.name for s in servers if s.name not in tag_channels_config]
        if missing:
            raise ValueError(
                "metrics_config.tag_channels is missing entries for server(s): "
                f"{', '.join(missing)}"
            )
    asyncio.run(run_all(servers))
