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

from lib.config import MetricType, config, settings
from lib.logging import config_logging
from lib.opcua_client import OPCUAClient
from lib.verify import get_plc_tags

from src.db import MetricsDatabase, TagsDatabase
from src.subscribers.opcua import (
    subscribe_cpu_usage,
    subscribe_kep_events,
    subscribe_network_usage,
    subscribe_opc_connection_events,
    subscribe_ram_usage,
    subscribe_service_info,
)

config_logging()
logger = logging.getLogger(__name__)


async def main():
    logger.info("Initiating KepServerLogger Central Collector...")
    logger.info(f"Connecting to {config.kepserver_server_url}...")

    tags_to_log = get_plc_tags()

    client = OPCUAClient(
        url=config.kepserver_server_url,
        app_uri=config.app_uri,
        name=config.application_name,
        cert_path=config.cert_path,
        key_path=config.key_path,
        username=config.kepserver_username,
        password=config.kepserver_password,
    )

    await client.setup()

    tags_db = TagsDatabase(retention_days=settings.log_retention_days)
    tags_db.initialize()

    metrics_db = MetricsDatabase(retention_days=settings.log_retention_days)
    metrics_db.initialize()

    logger.info("Initialization complete, starting main loop...")
    time.sleep(5)

    async with client:
        logger.info("OPC UA client connected, entering main loop")
        start_time = time.time()
        try:
            while True:
                if MetricType.PLC_TAGS in settings.metrics_to_log:
                    tag_values, timestamp = await client.read_batch(tags_to_log)
                    rows = tags_db.process_tag_values(tag_values, timestamp)
                    tags_db.save_many(rows)
                    logger.info(f"[TAGS] Saved {len(rows)} tags to the database")
                if MetricType.CPU in settings.metrics_to_log:
                    try:
                        cpu_usage = await subscribe_cpu_usage(client)
                        metrics_db.insert_cpu_usage(cpu_usage)
                        logger.info("[CPU] Logged CPU usage")
                    except Exception as e:
                        logger.warning(f"[CPU] Skipping: {e}")
                if MetricType.RAM in settings.metrics_to_log:
                    try:
                        ram_usage = await subscribe_ram_usage(client)
                        metrics_db.insert_ram_usage(ram_usage)
                        logger.info("[RAM] Logged RAM usage")
                    except Exception as e:
                        logger.warning(f"[RAM] Skipping: {e}")
                if MetricType.NETWORK in settings.metrics_to_log:
                    try:
                        network_usage = await subscribe_network_usage(client)
                        for network in network_usage:
                            metrics_db.insert_network_metrics(network)
                        logger.info(
                            f"[NETWORK] Logged network usage for {len(network_usage)} interfaces"
                        )
                    except Exception as e:
                        logger.warning(f"[NETWORK] Skipping: {e}")
                if MetricType.SERVICES in settings.metrics_to_log:
                    try:
                        service_info = await subscribe_service_info(client)
                        for service in service_info:
                            metrics_db.insert_service_info(service)
                        logger.info(
                            f"[SERVICES] Logged info for {len(service_info)} services"
                        )
                    except Exception as e:
                        logger.warning(f"[SERVICES] Skipping: {e}")
                if MetricType.KEPSERVER_EVENTS in settings.metrics_to_log:
                    try:
                        kep_events = await subscribe_kep_events(client)
                        for event in kep_events:
                            metrics_db.insert_event(event)
                        logger.info(
                            f"[EVENTS] Logged {len(kep_events)} KepServer events"
                        )
                    except Exception as e:
                        logger.warning(f"[EVENTS] Skipping: {e}")
                if MetricType.OPC_DIAGNOSTICS in settings.metrics_to_log:
                    try:
                        opc_events = await subscribe_opc_connection_events(client)
                        for event in opc_events:
                            metrics_db.insert_opc_connection_event(event)
                        logger.info(
                            f"[OPC_DIAGS] Logged {len(opc_events)} OPC connection events"
                        )
                    except Exception as e:
                        logger.warning(f"[OPC_DIAGS] Skipping: {e}")

                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Stopping logger...")

        finally:
            await client.disconnect()
            logger.info("OPC UA client disconnected, exiting main loop")
            logger.info(f"Total runtime: {time.time() - start_time:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(main())
