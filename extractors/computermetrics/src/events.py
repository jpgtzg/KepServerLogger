from __future__ import annotations

import hashlib
import os

import requests

from models import KepEvent


def get_events() -> list[KepEvent]:
    username = os.getenv("KEPSERVER_USERNAME")
    password = os.getenv("KEPSERVER_PASSWORD")
    url = os.getenv("EVENT_LOG_URL")

    if not username or not password or not url:
        raise RuntimeError(
            "Environment variables KEPSERVER_USERNAME, KEPSERVER_PASSWORD, and EVENT_LOG_URL must be set."
        )

    response = requests.get(url, auth=(username, password), timeout=30)
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
