import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

# ── .txt format (manually exported, one event per group of lines) ──────────
TIMESTAMP_RE = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\.\d+\s+(?:AM|PM))\s+\[([^\]]+)\]\s+(\S+)"
)
FIELD_RE = re.compile(r"^[\t ]*[0-9a-fA-F]+:\s{1,3}(.+)$")

# ── .log format (binary UTF-16-LE, events delimited by null bytes) ─────────
LOG_EVENT_RE = re.compile(
    r"\[([^\]\n]+)\]\s+(\w+)\s*\n\s*0+:\s+Event started(.*?)0+:\s+Event complete",
    re.DOTALL,
)
LOG_FIELD_SPLIT_RE = re.compile(r"0{10}:")


def parse_timestamp_txt(ts: str) -> datetime:
    return datetime.strptime(ts, "%m/%d/%Y %I:%M:%S.%f %p")


def parse_timestamp_utc(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _delta_seconds(t0: str, t1: str) -> float | None:
    """Seconds between two ISO timestamps. Returns None if either is empty/invalid."""
    if not t0 or not t1:
        return None
    try:
        a = datetime.fromisoformat(t0)
        b = datetime.fromisoformat(t1)
        return (b - a).total_seconds()
    except ValueError:
        return None


def extract_field_txt(line: str) -> tuple[str, str] | None:
    m = FIELD_RE.match(line)
    if not m:
        return None
    content = m.group(1).rstrip()
    if content in ("Event started", "Event complete"):
        return None
    if ":" not in content:
        return None
    key, _, value = content.partition(":")
    return key.strip(), value.strip()


def extract_field_binary(chunk: str) -> tuple[str, str] | None:
    chunk = chunk.strip()
    if not chunk or chunk in ("Event started", "Event complete"):
        return None
    if ":" not in chunk:
        return None
    key, _, value = chunk.partition(":")
    key = key.strip().rstrip()
    value = value.strip()
    if not key or not value or key[0].isdigit():
        return None
    if key in ("Request Header", "Response Header", "Parameters"):
        return None
    return key, value


@dataclass
class OpcEvent:
    timestamp: str
    session_tag: str
    event_type: str
    fields: dict = field(default_factory=dict)

    def get(self, *keys: str, default=None):
        for k in keys:
            if k in self.fields:
                return self.fields[k]
        return default


@dataclass
class ConnectionSpan:
    """One connect→disconnect episode for a client."""

    connected_at: str
    auth_token: str
    disconnected_at: str = ""
    disconnect_reason: str = ""


@dataclass
class ClientSession:
    application_name: str = ""
    application_uri: str = ""
    endpoint_url: str = ""
    username: str = ""
    session_id: str = ""
    auth_token: str = ""
    connected_at: str = ""
    activated_at: str = ""
    last_seen: str = ""
    disconnected_at: str = ""
    disconnect_reason: str = ""
    active: bool = False
    # History of previous connect/disconnect spans (all but the current one)
    past_connections: list = field(default_factory=list)  # list[ConnectionSpan]

    @property
    def reconnect_count(self) -> int:
        return len(self.past_connections)

    def total_downtime_seconds(self) -> float:
        """Sum of gap durations between consecutive connection spans."""
        spans = list(self.past_connections)
        # Append current span so we can look at transitions
        spans.append(
            ConnectionSpan(
                connected_at=self.connected_at,
                auth_token=self.auth_token,
                disconnected_at=self.disconnected_at,
            )
        )
        total = 0.0
        for i in range(len(spans) - 1):
            gap = _delta_seconds(spans[i].disconnected_at, spans[i + 1].connected_at)
            if gap is not None and gap > 0:
                total += gap
        return total

    def _push_reconnect(self, new_connected_at: str, new_auth_token: str = "") -> None:
        """Archive the current span and start a fresh one."""
        self.past_connections.append(
            ConnectionSpan(
                connected_at=self.connected_at,
                auth_token=self.auth_token,
                disconnected_at=self.disconnected_at,
                disconnect_reason=self.disconnect_reason,
            )
        )
        self.connected_at = new_connected_at
        self.auth_token = new_auth_token
        self.disconnected_at = ""
        self.disconnect_reason = ""
        self.active = False

    def summary(self) -> dict:
        d: dict = {
            "application_name": self.application_name,
            "application_uri": self.application_uri,
            "endpoint_url": self.endpoint_url,
            "username": self.username,
            "session_id": self.session_id,
            "auth_token": self.auth_token,
            "connected_at": self.connected_at,
            "activated_at": self.activated_at,
            "last_seen": self.last_seen,
            "disconnected_at": self.disconnected_at,
            "disconnect_reason": self.disconnect_reason,
            "active": self.active,
            "reconnect_count": self.reconnect_count,
            "total_downtime_seconds": round(self.total_downtime_seconds(), 1),
            "past_connections": [asdict(c) for c in self.past_connections],
        }
        return {k: v for k, v in d.items() if v not in ("", False, 0, [], 0.0)}


def _find_session(sessions: dict, tag: str) -> "ClientSession | None":
    return sessions.get(f"i={tag}") or sessions.get(tag)


# ── Parsers ────────────────────────────────────────────────────────────────


def parse_log_txt(filepath: str) -> list[OpcEvent]:
    with open(filepath, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    events: list[OpcEvent] = []
    current: OpcEvent | None = None

    for line in lines:
        m = TIMESTAMP_RE.match(line)
        if m:
            current = OpcEvent(
                timestamp=m.group(1).strip(),
                session_tag=m.group(2).strip(),
                event_type=m.group(3).strip(),
            )
            events.append(current)
            continue

        if current is None:
            continue

        pair = extract_field_txt(line)
        if pair:
            key, value = pair
            if value:
                current.fields[key] = value

    return events


def parse_log_binary(filepath: str) -> list[OpcEvent]:
    with open(filepath, "rb") as f:
        data = f.read()

    text = data.decode("utf-16-le", errors="ignore").replace("\x00", "\n")

    events: list[OpcEvent] = []
    for m in LOG_EVENT_RE.finditer(text):
        tag = m.group(1).strip()
        etype = m.group(2).strip()
        content = m.group(3)

        fields: dict[str, str] = {}
        for chunk in LOG_FIELD_SPLIT_RE.split(content):
            pair = extract_field_binary(chunk)
            if pair:
                key, value = pair
                if key not in fields:
                    fields[key] = value

        timestamp = fields.get("timestamp (UTC)", "")

        events.append(
            OpcEvent(
                timestamp=timestamp,
                session_tag=tag,
                event_type=etype,
                fields=fields,
            )
        )

    return events


def detect_format(filepath: str) -> str:
    with open(filepath, "rb") as f:
        sample = f.read(8192)
    if not sample:
        return "txt"
    null_ratio = sample.count(0) / len(sample)
    return "binary" if null_ratio > 0.3 else "txt"


def parse_log(filepath: str) -> list[OpcEvent]:
    fmt = detect_format(filepath)
    if fmt == "binary":
        return parse_log_binary(filepath)
    return parse_log_txt(filepath)


# ── Session map builders ───────────────────────────────────────────────────


def build_client_map(events: list[OpcEvent]) -> dict[str, ClientSession]:
    sessions: dict[str, ClientSession] = {}
    pending: dict[str, ClientSession] = {}
    by_app_name: dict[str, ClientSession] = {}

    for ev in events:
        tag = ev.session_tag
        etype = ev.event_type

        if etype == "CreateSessionRequest":
            raw_name = ev.get("applicationName", default="")
            app_name = raw_name.split("|", 1)[-1] if "|" in raw_name else raw_name
            existing = by_app_name.get(app_name)

            if existing:
                old_key = existing.auth_token or existing.session_id
                if old_key in sessions:
                    del sessions[old_key]
                existing._push_reconnect(ev.timestamp)
                pending[tag] = existing
            else:
                s = ClientSession(
                    application_name=app_name,
                    application_uri=ev.get("applicationUri", default=""),
                    endpoint_url=ev.get("endpointUrl", default=""),
                    connected_at=ev.timestamp,
                )
                pending[tag] = s
                by_app_name[app_name] = s

        elif etype == "CreateSessionResponse":
            result = ev.get("serviceResult", default="")
            if result and "Good" not in result:
                pending.pop(tag, None)
                continue
            session_id = ev.get("sessionId", default="")
            new_token = ev.get("authenticationToken", default="")
            s = pending.pop(tag, None)
            if s is None:
                continue
            s.session_id = session_id
            s.auth_token = new_token
            s.active = True
            key = new_token or session_id
            sessions[key] = s
            by_app_name.setdefault(s.application_name, s)

        elif etype == "ActivateSessionRequest":
            s = _find_session(sessions, tag)
            if s and s.active:
                username = ev.get("userName", default="")
                if username:
                    s.username = username
                s.activated_at = ev.timestamp

        elif etype == "ActivateSessionResponse":
            result = ev.get("serviceResult", default="")
            s = _find_session(sessions, tag)
            if s and result and "Good" not in result:
                s.active = False
                s.disconnect_reason = f"Fault:{result}"

        elif etype == "ServiceFaultResponse":
            result = ev.get("serviceResult", default="")
            auth = ev.get("authenticationToken", default="")
            s = _find_session(sessions, tag) or (sessions.get(auth) if auth else None)
            if s and s.active:
                s.active = False
                s.disconnected_at = ev.timestamp
                s.disconnect_reason = f"Fault:{result}" if result else "Fault"

        elif etype == "CloseSessionRequest":
            auth = ev.get("authenticationToken", default="")
            s = _find_session(sessions, tag) or (sessions.get(auth) if auth else None)
            if s:
                s.active = False
                s.disconnected_at = ev.timestamp
                s.disconnect_reason = "CloseSession"

    return sessions


def build_active_map(events: list[OpcEvent]) -> dict[str, ClientSession]:
    sessions: dict[str, ClientSession] = {}

    SKIP_TAGS = {"NoSession", "AnonymousClient"}
    REQUEST_TYPES = {
        "ReadRequest",
        "WriteRequest",
        "ActivateSessionRequest",
        "CreateSessionRequest",
        "CloseSessionRequest",
    }

    for ev in events:
        tag = ev.session_tag
        if tag in SKIP_TAGS:
            continue
        if tag.startswith("opc.tcp://"):
            continue

        if tag not in sessions:
            sessions[tag] = ClientSession(
                application_name=tag,
                connected_at=ev.timestamp,
                active=True,
            )

        s = sessions[tag]

        auth = ev.get("authenticationToken", default="")
        if auth and auth != "i=0" and not s.auth_token:
            s.auth_token = auth

        if ev.event_type in REQUEST_TYPES and ev.timestamp:
            s.last_seen = ev.timestamp

        if ev.event_type == "CloseSessionRequest":
            s.active = False
            s.disconnected_at = ev.timestamp
            s.disconnect_reason = "CloseSession"
        elif ev.event_type == "ServiceFaultResponse":
            result = ev.get("serviceResult", default="")
            s.active = False
            s.disconnected_at = ev.timestamp
            s.disconnect_reason = f"Fault:{result}" if result else "Fault"

    return sessions


def build_sessions(events: list[OpcEvent]) -> dict[str, ClientSession]:
    active = build_active_map(events)
    handshake = build_client_map(events)

    handshake_by_token: dict[str, ClientSession] = {
        s.auth_token: s for s in handshake.values() if s.auth_token
    }

    merged: dict[str, ClientSession] = {}
    for tag, s in active.items():
        rich = handshake_by_token.get(s.auth_token)
        if rich:
            rich.last_seen = rich.last_seen or s.last_seen
            merged[tag] = rich
        else:
            merged[tag] = s

    tagged = {s.application_name for s in merged.values()}
    for s in handshake.values():
        if s.application_name not in tagged:
            merged[s.auth_token or s.session_id] = s

    return merged
