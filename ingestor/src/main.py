"""
Ingestor for retrieving data from the OPC UA server and ingesting it into the database.
"""

import asyncio
import logging

from lib.heartbeat import SystemHeartbeatHandler
from lib.logging import config_logging, current_server
from lib.metrics import METRICS
from lib.opcua_client import OPCUAClient
from lib.servers import ServerConfig, load_servers_configs
from lib.subscription import NodeSubscription, SubscriptionConfig
from lib.utils import (
    AGENT_HEARTBEAT_RECEIVE_PATH,
    AGENT_HEARTBEAT_SEND_PATH,
    COLLECTOR_HEARTBEAT_RECEIVE_PATH,
    COLLECTOR_HEARTBEAT_SEND_PATH,
    MAX_HEARTBEAT_NUMBER,
    OPCUA_REQUEST_TIMEOUT_SECONDS,
    RECONNECT_DELAY,
)

from src.channels import get_channel_tags
from src.db import IngestorDatabase
from src.ingest import Ingest
from src.jobs import monitor_subscriptions
from src.state import config, settings

config_logging()
logger = logging.getLogger(__name__)


async def main(server: ServerConfig):
    current_server.set(server.name)
    logger.info(f"[{server.name}] Initiating IDL Central Collector...")

    channel_tags = get_channel_tags(server)

    db = IngestorDatabase(
        host=config.db_host,
        port=config.db_port,
        db_name=server.db_name,
        user=config.db_user,
        password=config.db_password,
        retention_days=settings.log_retention_days,
    )
    db.initialize()
    ingest = Ingest(db, f"[{server.name}]")

    try:
        while True:
            try:
                await _run_session(server, db, ingest, channel_tags)
            except asyncio.CancelledError:
                db.log_status("inactive", reason="shutdown")
                logger.info(f"[{server.name}] Shutting down.")
                raise
            except Exception as e:
                reasons = e.exceptions if isinstance(e, BaseExceptionGroup) else (e,)
                error_id = db.log_event("ERROR", "RECONNECT", reasons[0])
                db.log_status("inactive", error_id=error_id)
                logger.exception(
                    f"[{server.name}] Connection lost ("
                    + "; ".join(f"{type(r).__name__}: {r}" for r in reasons)
                    + f"). Retrying in {RECONNECT_DELAY}s..."
                )
                await asyncio.sleep(RECONNECT_DELAY)
    finally:
        db.close()


def _build_subscriptions(
    client: OPCUAClient,
    server: ServerConfig,
    ingest: Ingest,
    channel_tags: dict[str, dict[str, str]],
) -> list[NodeSubscription]:
    """One subscription per enabled metric and one per tag channel."""
    subscriptions = [
        NodeSubscription(
            client,
            f"[{server.name}][{name.upper()}]",
            {name: METRICS[name].node_id(settings.node_prefix)},
            METRICS[name].config.for_publish_interval(
                settings.polling_interval_seconds
            ),
            ingest.on_metric,
        )
        for name in settings.metrics
    ]
    for channel, tags in channel_tags.items():
        label = f"[{server.name}][{channel.upper()}]"
        if not tags:
            logger.info(f"{label} No tags found for this channel, skipping.")
            continue
        subscriptions.append(
            NodeSubscription(client, label, tags, SubscriptionConfig(), ingest.on_tag)
        )
    return subscriptions


async def _run_session(
    server: ServerConfig,
    db: IngestorDatabase,
    ingest: Ingest,
    channel_tags: dict[str, dict[str, str]],
) -> None:
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
        host_name = await client.get_node(settings.host_name_node).read_value()
        db.log_status("active", host_name=host_name)
        logger.info(f"[{server.name}] Connected — host: {host_name}")

        collector_heartbeat = SystemHeartbeatHandler(
            client=client,
            max_heartbeat=MAX_HEARTBEAT_NUMBER,
            echo=False,
            send_path=COLLECTOR_HEARTBEAT_SEND_PATH,
            pair="collector",
            on_rtt=lambda rtt: ingest.add_model("heartbeat_rtt", rtt),
            receive_path=COLLECTOR_HEARTBEAT_RECEIVE_PATH,
            max_rtt=settings.polling_interval_seconds * 2,
            stale_after=settings.polling_interval_seconds * 5,
        )
        agent_heartbeat = SystemHeartbeatHandler(
            client=client,
            max_heartbeat=MAX_HEARTBEAT_NUMBER,
            echo=True,
            send_path=AGENT_HEARTBEAT_SEND_PATH,
            pair="agent",
            receive_path=AGENT_HEARTBEAT_RECEIVE_PATH,
            max_rtt=settings.polling_interval_seconds * 2,
            stale_after=settings.polling_interval_seconds * 5,
        )
        ingest.new_session(settings.metrics)
        subscriptions = _build_subscriptions(client, server, ingest, channel_tags)
        try:
            await collector_heartbeat.start(
                on_stale=lambda: db.log_event(
                    "WARNING", "SYSTEM-HEARTBEAT", TimeoutError("Heartbeat is stale")
                )
            )
            await agent_heartbeat.start()
            for subscription in subscriptions:
                await subscription.start()
            async with asyncio.TaskGroup() as tg:
                tg.create_task(ingest.run())
                tg.create_task(monitor_subscriptions(subscriptions, db))
        finally:
            await asyncio.gather(
                *(s.stop() for s in subscriptions), return_exceptions=True
            )
            await collector_heartbeat.stop()
            await agent_heartbeat.stop()
            await ingest.flush()


async def run_all(servers: list) -> None:
    results = await asyncio.gather(*[main(s) for s in servers], return_exceptions=True)
    for server, result in zip(servers, results):
        if isinstance(result, Exception):
            logger.error(
                f"[{server.name}] Stopped unexpectedly: {result}", exc_info=result
            )


if __name__ == "__main__":
    asyncio.run(run_all(load_servers_configs()))
