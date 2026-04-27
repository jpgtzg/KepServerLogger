"""
connection_log.py — minimal connection event extractor.

Walks the raw OPC UA event stream and emits one ConnectionEvent per
connect/disconnect transition, in chronological order.

Usage:
    from lib.connection_log import get_connection_events
    for ev in get_connection_events("opcdiags.log"):
        print(ev)
"""

from dataclasses import dataclass
from lib.opc_parser import parse_log, OpcEvent


@dataclass
class ConnectionEvent:
    timestamp: str
    client_name: str
    kind: str        # "connected" or "disconnected"
    reason: str = ""

    def __str__(self) -> str:
        suffix = f" ({self.reason})" if self.reason else ""
        return f"[{self.timestamp}] {self.client_name} {self.kind}{suffix}"


def get_connection_events(filepath: str) -> list[ConnectionEvent]:
    """
    Parse *filepath* and return a chronological list of ConnectionEvents.

    A "connected" event is emitted on CreateSessionRequest (when the client
    name is first known). A "disconnected" event is emitted on
    CloseSessionRequest or ServiceFaultResponse.
    """
    events = parse_log(filepath)
    return _extract(events)


_SKIP_TAGS = {"NoSession", "AnonymousClient"}
_ACTIVITY_TYPES = {"ReadRequest", "WriteRequest", "ActivateSessionRequest"}


def _extract(events: list[OpcEvent]) -> list[ConnectionEvent]:
    # tag → client name; populated on CreateSessionRequest or first activity
    tag_to_name: dict[str, str] = {}
    result: list[ConnectionEvent] = []

    for ev in events:
        tag = ev.session_tag
        etype = ev.event_type

        # Mid-session heuristic: first activity from an unknown tag → connected
        if etype in _ACTIVITY_TYPES and tag not in tag_to_name and tag not in _SKIP_TAGS and not tag.startswith("opc.tcp://"):
            tag_to_name[tag] = tag
            result.append(ConnectionEvent(
                timestamp=ev.timestamp,
                client_name=tag,
                kind="connected",
            ))

        if etype == "CreateSessionRequest":
            raw = ev.get("applicationName", default="")
            name = raw.split("|", 1)[-1] if "|" in raw else raw
            name = name or tag
            tag_to_name[tag] = name
            result.append(ConnectionEvent(
                timestamp=ev.timestamp,
                client_name=name,
                kind="connected",
            ))

        elif etype == "CloseSessionRequest":
            name = tag_to_name.get(tag, tag)
            result.append(ConnectionEvent(
                timestamp=ev.timestamp,
                client_name=name,
                kind="disconnected",
                reason="CloseSession",
            ))

        elif etype == "ServiceFaultResponse":
            name = tag_to_name.get(tag, tag)
            fault = ev.get("serviceResult", default="Fault")
            result.append(ConnectionEvent(
                timestamp=ev.timestamp,
                client_name=name,
                kind="disconnected",
                reason=fault,
            ))

    return result
