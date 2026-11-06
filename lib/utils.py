from datetime import datetime, timezone

TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
RECONNECT_DELAY = 5
MAX_CONSECUTIVE_METRIC_FAILURES = 3
OPCUA_REQUEST_TIMEOUT_SECONDS = 30

MAX_HEARTBEAT_NUMBER = 255
HEARTBEAT_INTERVAL_SECONDS = 5
MAX_BUFFERED_RTTS = 999
MAX_BUFFERED_ERRORS = 999
# One publish must stay well under the OPC UA string size limit.
MAX_ERRORS_PER_PUBLISH = 50
MAX_ERROR_TRACEBACK_CHARS = 4000

COLLECTOR_HEARTBEAT_SEND_PATH = "ns=2;s=IDL.Metrics.Heartbeat.collector_send"
COLLECTOR_HEARTBEAT_RECEIVE_PATH = "ns=2;s=IDL.Metrics.Heartbeat.collector_receive"
AGENT_HEARTBEAT_SEND_PATH = "ns=2;s=IDL.Metrics.Heartbeat.agent_send"
AGENT_HEARTBEAT_RECEIVE_PATH = "ns=2;s=IDL.Metrics.Heartbeat.agent_receive"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
