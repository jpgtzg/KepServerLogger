from lib.config import settings
from lib.opcua_client import OPCUAClient
from lib.models import KepEvent
import json


async def subscribe_kep_events(client: OPCUAClient) -> None:
    node = client.get_node(f"{settings.metrics_config.events.prefix}.batch")
    raw: str = await node.read_value()
    if not raw:
        return []
    return [KepEvent(**e) for e in json.loads(raw)]
