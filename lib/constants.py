from datetime import datetime

PREFIX = "ns=2;s="
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

def format_timestamp(ts):
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts.strftime(TIMESTAMP_FORMAT)
    try:
        return ts.isoformat()
    except AttributeError:
        return str(ts)
