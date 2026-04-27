import hashlib
from datetime import datetime, timezone

from lib.connection_log import get_connection_events
from lib.models import OpcConnectionEvent


def _normalize_timestamp(ts: str) -> datetime:
    """Parse any log timestamp format and return a UTC-aware datetime."""
    try:
        return datetime.strptime(ts, "%m/%d/%Y %I:%M:%S.%f %p").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        pass
    dt = datetime.fromisoformat(ts)
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def get_opc_connection_events(log_path: str) -> list[OpcConnectionEvent]:
    raw_events = get_connection_events(log_path)
    result: list[OpcConnectionEvent] = []
    for ev in raw_events:
        if not ev.timestamp:
            continue
        normalized_ts = _normalize_timestamp(ev.timestamp)
        prehash = f"{ev.timestamp}|{ev.client_name}|{ev.kind}|{ev.reason}"
        event_hash = hashlib.sha256(prehash.encode("utf-8")).hexdigest().upper()
        try:
            result.append(
                OpcConnectionEvent(
                    timestamp=normalized_ts,
                    client_name=ev.client_name,
                    kind=ev.kind,
                    reason=ev.reason,
                    hash=event_hash,
                )
            )
        except Exception:
            continue
    return result
