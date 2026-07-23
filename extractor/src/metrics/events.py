from __future__ import annotations

import hashlib
import requests

from lib.models import KepEvent
from src.state import config

def get_kepserver_events() -> list[KepEvent]:
    response = requests.get(
        config.kepserver_event_log_url,
        auth=(config.kepserver_username, config.kepserver_password),
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []

    events: list[KepEvent] = []
    for item in payload:
        timestamp = str(item.get("timestamp", ""))
        name = str(item.get("event", ""))
        source = str(item.get("source", ""))
        message = str(item.get("message", ""))
        prehash = f"{name}|{source}|{message}|{timestamp}"
        event_hash = hashlib.sha256(prehash.encode("utf-8")).hexdigest().upper()

        events.append(
            KepEvent(
                timestamp=timestamp,
                name=name,
                source=source,
                message=message,
                hash=event_hash,
            )
        )

    return events
