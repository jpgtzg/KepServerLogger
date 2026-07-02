"""
Ingestor for retrieving data from the OPC UA server and ingesting it into the database.

Reads the tags from a .csv file and ingests the data into the database.

## This ingestor will log the following metrics:
- Tags

- CPU Usage
- RAM Usage
- Network Usage
- Services Usage
- KepServer Events
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

from lib.config import Config
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

config = Config()  # pyright: ignore[reportCallIssue]
settings = Settings.load()
OPCUAModel.configure(timestamp_format=settings.timestamp_format)


async def main(server: ServerConfig):
    server_name = server.name
    logger.info(f"[{server_name}] Initiating KepServerLogger Central Collector...")
    logger.info(f"[{server_name}] Connecting to {server.url}...")

    channel_tags = {
        channel: get_tags(channel, server, settings.metrics_config)
        for channel in settings.metrics_config.tag_channels
    }

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

    db = IngestorDatabase(
        host=config.db_host,
        port=config.db_port,
        db_name=server.db_name,
        user=config.db_user,
        password=config.db_password,
        retention_days=settings.log_retention_days,
    )
    db.initialize()

    logger.info(f"[{server_name}] Initialization complete, starting main loop...")
    time.sleep(5)

    async with client:
        logger.info(f"[{server_name}] OPC UA client connected, entering main loop")
        start_time = time.time()
        try:
            while True:
                if MetricType.TAG_CHANNELS in settings.metrics_to_log:
                    try:
                        for channel, tags in channel_tags.items():
                            tag_values, timestamp = await client.read_batch(
                                tags=tags,
                                prefix=settings.metrics_config.tag_channels[channel],
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
                        cpu_usage = await subscribe_cpu_usage(
                            client, settings.metrics_config
                        )
                        db.insert_cpu_usage(cpu_usage)
                        logger.info(f"[{server_name}][CPU] Logged CPU usage")
                    except Exception as e:
                        logger.warning(f"[{server_name}][CPU] Skipping: {e}")
                if MetricType.RAM in settings.metrics_to_log:
                    try:
                        ram_usage = await subscribe_ram_usage(
                            client, settings.metrics_config
                        )
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
                        kep_events = await subscribe_kep_events(
                            client, settings.metrics_config
                        )
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
                try:
                    host_name = await subscribe_host_name(
                        client, settings.metrics_config
                    )
                    db.insert_host_name(host_name, datetime.now(timezone.utc))
                    logger.info(
                        f"[{server_name}][HOST_NAME] Logged host name: {host_name}"
                    )
                except Exception as e:
                    logger.warning(f"[{server_name}][HOST_NAME] Skipping: {e}")
                await asyncio.sleep(settings.polling_interval_seconds)

        except KeyboardInterrupt:
            logger.info(f"[{server_name}] Stopping logger...")
        except Exception as e:
            logger.error(
                f"[{server_name}] Fatal error in main loop: {type(e).__name__}: {e}",
                exc_info=True,
            )

        finally:
            await client.disconnect()
            logger.info(
                f"[{server_name}] OPC UA client disconnected, exiting main loop"
            )
            logger.info(
                f"[{server_name}] Total runtime: {time.time() - start_time:.2f} seconds"
            )


async def run_all(servers: list) -> None:
    await asyncio.gather(*[main(s) for s in servers])


if __name__ == "__main__":
    servers = load_servers_configs()
    asyncio.run(run_all(servers))
