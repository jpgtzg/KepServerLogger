"""
Timeout-bounded tag reads, with a per-tag fallback so one dead tag can't take a
whole batched read down with it.
"""

import asyncio
import logging
import time

from asyncua import ua

from lib.opcua_client import OPCUAClient
from lib.utils import TAG_QUARANTINE_RETRY_SECONDS, TAG_READ_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


async def read_with_timeout(client: OPCUAClient, tags: list[str], prefix: str):
    return await asyncio.wait_for(
        client.read_batch(tags=tags, prefix=prefix), TAG_READ_TIMEOUT_SECONDS
    )


async def read_individually(
    client: OPCUAClient,
    tags: list[str],
    prefix: str,
    quarantined: dict[str, float],
    label: str,
):
    """
    Fallback after a failed batch: read each tag alone, quarantine the ones that
    time out and keep the rest. Raises only if no tag could be read at all, which
    points at the connection rather than at individual tags.
    """
    # Concurrent, so N dead tags cost one timeout instead of N.
    results = await asyncio.gather(
        *(read_with_timeout(client, [tag], prefix) for tag in tags),
        return_exceptions=True,
    )
    tag_values = []
    timestamp = None
    for tag, result in zip(tags, results):
        if isinstance(result, (TimeoutError, ua.UaError)):
            quarantined[tag] = time.monotonic() + TAG_QUARANTINE_RETRY_SECONDS
            logger.warning(
                f"{label} Tag {tag} not responding, quarantined for "
                f"{TAG_QUARANTINE_RETRY_SECONDS}s"
            )
        elif isinstance(result, BaseException):
            raise result
        else:
            values, timestamp = result
            tag_values.extend(values)
    if timestamp is None:
        raise TimeoutError(f"{label} None of {len(tags)} tags could be read")
    return tag_values, timestamp
