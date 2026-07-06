"""
Ingestor for retrieving data from the OPC UA server and ingesting it into the database.
"""

import asyncio
import logging

from lib.config import IngestorConfig
from lib.logging import config_logging
from lib.models import OPCUAModel
from lib.opcua_client import OPCUAClient
from lib.servers import ServerConfig, load_servers_configs
from lib.settings import MetricType, Settings
from lib.utils import get_tags

from src.db import IngestorDatabase
from src.subscribers.opcua import (
    subscribe_cpu_usage,
    subscribe_host_name,
    subscribe_kep_events,
    subscribe_network_usage,
    subscribe_opc_connection_events,
    subscribe_ram_usage,
    subscribe_service_info,
)

config_logging()
logger = logging.getLogger(__name__)

config = IngestorConfig()  # pyright: ignore[reportCallIssue]
settings = Settings.load()
OPCUAModel.configure(timestamp_format=settings.timestamp_format)

_RETRY_DELAYS = [5, 10, 20, 40, 60]


async def _poll_loop(
    server_name: str, client: OPCUAClient, db: IngestorDatabase, channel_tags: dict
) -> None:
    while True:
        tag_channels_config = settings.metrics_config.tag_channels
        if (
            MetricType.TAG_CHANNELS in settings.metrics_to_log
            and tag_channels_config is not None
        ):
            try:
                for channel, tags in channel_tags.items():
                    if not tags:
                        logger.info(
                            f"[{server_name}][{channel.upper()}] No tags found, skipping."
                        )
                        continue
                    tag_values, timestamp = await client.read_batch(
                        tags=tags,
                        prefix=tag_channels_config[channel],
                    )
                    rows = db.process_tag_values(tag_values, timestamp)
                    db.save_many(rows)
                    logger.info(
                        f"[{server_name}][{channel.upper()}] Saved {len(rows)} values from {len(tags)} tags"
                    )
            except Exception as e:
                logger.warning(f"[{server_name}][TAG_CHANNELS] Skipping: {e}")
        if MetricType.CPU in settings.metrics_to_log:
            try:
                cpu_usage = await subscribe_cpu_usage(client, settings.metrics_config)
                db.insert_cpu_usage(cpu_usage)
                logger.info(f"[{server_name}][CPU] Logged CPU usage")
            except Exception as e:
                logger.warning(f"[{server_name}][CPU] Skipping: {e}")
        if MetricType.RAM in settings.metrics_to_log:
            try:
                ram_usage = await subscribe_ram_usage(client, settings.metrics_config)
                db.insert_ram_usage(ram_usage)
                logger.info(f"[{server_name}][RAM] Logged RAM usage")
            except Exception as e:
                logger.warning(f"[{server_name}][RAM] Skipping: {e}")
        if MetricType.NETWORK in settings.metrics_to_log:
            try:
                network_usage = await subscribe_network_usage(
                    client, settings.metrics_config
                )
                for network in network_usage:
                    db.insert_network_metrics(network)
                logger.info(
                    f"[{server_name}][NETWORK] Logged {len(network_usage)} interfaces"
                )
            except Exception as e:
                logger.warning(f"[{server_name}][NETWORK] Skipping: {e}")
        if MetricType.SERVICES in settings.metrics_to_log:
            try:
                service_info = await subscribe_service_info(
                    client, settings.metrics_config
                )
                for service in service_info:
                    db.insert_service_info(service)
                logger.info(
                    f"[{server_name}][SERVICES] Logged {len(service_info)} services"
                )
            except Exception as e:
                logger.warning(f"[{server_name}][SERVICES] Skipping: {e}")
        if MetricType.KEPSERVER_EVENTS in settings.metrics_to_log:
            try:
                kep_events = await subscribe_kep_events(client, settings.metrics_config)
                for event in kep_events:
                    db.insert_event(event)
                logger.info(
                    f"[{server_name}][EVENTS] Logged {len(kep_events)} KepServer events"
                )
            except Exception as e:
                logger.warning(f"[{server_name}][EVENTS] Skipping: {e}")
        if MetricType.OPC_DIAGNOSTICS in settings.metrics_to_log:
            try:
                opc_events = await subscribe_opc_connection_events(
                    client, settings.metrics_config
                )
                for event in opc_events:
                    db.insert_opc_connection_event(event)
                logger.info(
                    f"[{server_name}][OPC_DIAGS] Logged {len(opc_events)} OPC connection events"
                )
            except Exception as e:
                logger.warning(f"[{server_name}][OPC_DIAGS] Skipping: {e}")
        await asyncio.sleep(settings.polling_interval_seconds)


async def main(server: ServerConfig):
    s = server.name
    logger.info(f"[{s}] Initiating KepServerLogger Central Collector...")

    tag_channels_config = settings.metrics_config.tag_channels
    channel_tags = (
        {
            channel: get_tags(channel, server, settings.metrics_config)
            for channel in tag_channels_config
        }
        if MetricType.TAG_CHANNELS in settings.metrics_to_log
        and tag_channels_config is not None
        else {}
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
            logger.info(f"[{s}] Connecting to {server.url}...")
            client = OPCUAClient(
                url=server.url,
                app_uri=config.app_uri,
                name=config.application_name,
                cert_path=server.cert_path,
                key_path=server.key_path,
                username=server.username,
                password=server.password,
            )
            await client.setup()

            async with client:
                host_name = await subscribe_host_name(client, settings.metrics_config)
                db.log_connection("connected", host_name=host_name)
                logger.info(f"[{s}] Connected — host: {host_name}")
                retry_count = 0

                await _poll_loop(s, client, db, channel_tags)

        except (KeyboardInterrupt, asyncio.CancelledError):
            db.log_connection("disconnected", reason="shutdown")
            logger.info(f"[{s}] Shutting down.")
            raise

        except Exception as e:
            delay = _RETRY_DELAYS[min(retry_count, len(_RETRY_DELAYS) - 1)]
            db.log_connection("disconnected", reason=f"{type(e).__name__}: {e}")
            logger.error(
                f"[{s}] Connection lost: {type(e).__name__}: {e}. "
                f"Retrying in {delay}s... (attempt {retry_count + 1})",
                exc_info=True,
            )
            retry_count += 1
            await asyncio.sleep(delay)


async def run_all(servers: list) -> None:
    await asyncio.gather(*[main(s) for s in servers])


if __name__ == "__main__":
    servers = load_servers_configs()
    asyncio.run(run_all(servers))
