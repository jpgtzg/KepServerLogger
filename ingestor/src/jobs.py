"""
Periodic checks that run next to the subscriptions of one session.
"""

import asyncio
import logging

from lib.subscription import NodeSubscription

from src.db import IngestorDatabase

logger = logging.getLogger(__name__)

HEALTH_CHECK_INTERVAL_SECONDS = 5


async def monitor_subscriptions(
    subscriptions: list[NodeSubscription], db: IngestorDatabase
) -> None:
    """
    Asks every subscription whether it is healthy. One the server ended raises
    ConnectionError, which ends the session so the caller reconnects; one that has
    gone silent is only logged, since a quiet plant is legitimate.
    """
    while True:
        await asyncio.sleep(HEALTH_CHECK_INTERVAL_SECONDS)
        for subscription in subscriptions:
            message = subscription.check_health()
            if message is not None:
                logger.warning(message)
                db.log_event("WARNING", "SUBSCRIPTION", TimeoutError(message))
