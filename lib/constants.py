from datetime import datetime

def format_timestamp(ts, timestamp_format: str):
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts.strftime(timestamp_format)
    try:
        return ts.isoformat()
    except AttributeError:
        return str(ts)
