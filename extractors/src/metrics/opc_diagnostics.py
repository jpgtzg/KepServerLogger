import hashlib
import os
from datetime import datetime, timezone

from lib.models import OpcConnectionEvent
from lib.opc_parser import LOG_EVENT_RE, LOG_FIELD_SPLIT_RE, OpcEvent, extract_field_binary

_ACTIVITY_TYPES = frozenset({"ReadRequest", "WriteRequest", "ActivateSessionRequest"})
_SKIP_TAGS = frozenset({"NoSession", "AnonymousClient"})


def _normalize_timestamp(ts: str) -> datetime:
    try:
        return datetime.strptime(ts, "%m/%d/%Y %I:%M:%S.%f %p").replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    dt = datetime.fromisoformat(ts)
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _make_model(timestamp: str, client_name: str, kind: str, reason: str = "") -> OpcConnectionEvent:
    normalized_ts = _normalize_timestamp(timestamp)
    prehash = f"{timestamp}|{client_name}|{kind}|{reason}"
    event_hash = hashlib.sha256(prehash.encode()).hexdigest().upper()
    return OpcConnectionEvent(
        timestamp=normalized_ts,
        client_name=client_name,
        kind=kind,
        reason=reason,
        hash=event_hash,
    )


class OpcDiagnosticsReader:
    """
    Tail-follow reader for binary opcdiags.log.

    Opens the file once, seeks to the current end (skipping history), and on
    each call returns only events appended since the last read.  Committed byte
    offset advances only past fully-matched events, so a partial event at the
    tail is retried on the next call.
    """

    def __init__(self, log_path: str):
        self._log_path = log_path
        self._file = None
        self._byte_offset: int = 0      # committed position (end of last complete event)
        self._raw_buffer: bytes = b""   # bytes after _byte_offset (may hold a partial event)
        self._tag_to_name: dict[str, str] = {}

    def _ensure_open(self) -> None:
        if self._file is None or self._file.closed:
            self._file = open(self._log_path, "rb")
            self._byte_offset = 0
            self._raw_buffer = b""

    def _handle_rotation(self) -> None:
        try:
            size = os.path.getsize(self._log_path)
        except OSError:
            return
        if size < self._byte_offset:
            self._byte_offset = 0
            self._raw_buffer = b""
            if self._file and not self._file.closed:
                self._file.close()
            self._file = None
            self._tag_to_name.clear()

    def close(self) -> None:
        if self._file and not self._file.closed:
            self._file.close()

    def read_new_events(self) -> list[OpcConnectionEvent]:
        try:
            self._handle_rotation()
            self._ensure_open()

            self._file.seek(self._byte_offset + len(self._raw_buffer))
            new_data = self._file.read()
            if not new_data:
                return []

            self._raw_buffer += new_data

            # Ensure even byte count for correct UTF-16-LE decoding
            raw = self._raw_buffer if len(self._raw_buffer) % 2 == 0 else self._raw_buffer[:-1]
            text = raw.decode("utf-16-le", errors="ignore").replace("\x00", "\n")

            opc_events: list[OpcEvent] = []
            last_end = 0
            for m in LOG_EVENT_RE.finditer(text):
                tag = m.group(1).strip()
                etype = m.group(2).strip()
                fields: dict[str, str] = {}
                for seg in LOG_FIELD_SPLIT_RE.split(m.group(3)):
                    pair = extract_field_binary(seg)
                    if pair:
                        k, v = pair
                        fields.setdefault(k, v)
                opc_events.append(OpcEvent(
                    timestamp=fields.get("timestamp (UTC)", ""),
                    session_tag=tag,
                    event_type=etype,
                    fields=fields,
                ))
                last_end = m.end()

            if last_end > 0:
                # Each BMP character is exactly 2 bytes in UTF-16-LE
                committed = last_end * 2
                self._byte_offset += committed
                self._raw_buffer = self._raw_buffer[committed:]

            return self._extract(opc_events)

        except Exception:
            return []

    def _extract(self, events: list[OpcEvent]) -> list[OpcConnectionEvent]:
        result: list[OpcConnectionEvent] = []
        for ev in events:
            tag = ev.session_tag
            etype = ev.event_type

            if (etype in _ACTIVITY_TYPES
                    and tag not in self._tag_to_name
                    and tag not in _SKIP_TAGS
                    and not tag.startswith("opc.tcp://")):
                self._tag_to_name[tag] = tag
                if ev.timestamp:
                    result.append(_make_model(ev.timestamp, tag, "connected"))

            elif etype == "CreateSessionRequest":
                raw = ev.get("applicationName", default="")
                name = raw.split("|", 1)[-1] if "|" in raw else raw
                name = name or tag
                self._tag_to_name[tag] = name
                if ev.timestamp:
                    result.append(_make_model(ev.timestamp, name, "connected"))

            elif etype == "CloseSessionRequest":
                name = self._tag_to_name.get(tag, tag)
                if ev.timestamp:
                    result.append(_make_model(ev.timestamp, name, "disconnected", "CloseSession"))

            elif etype == "ServiceFaultResponse":
                name = self._tag_to_name.get(tag, tag)
                fault = ev.get("serviceResult", default="Fault")
                if ev.timestamp:
                    result.append(_make_model(ev.timestamp, name, "disconnected", fault))

        return result
