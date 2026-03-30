from lib.models import Tag
from lib.constants import format_timestamp
from lib.config import Config

config = Config()

def process_tag_values(tag_values, timestamp: str):
    rows = []
    for tag_name, data_value in tag_values:
        source_ts = format_timestamp(
            data_value.SourceTimestamp, config.timestamp_format
        )
        rows.append(
            Tag(
                tag_name,
                str(data_value.Value.Value),
                data_value.StatusCode.name,
                source_ts,
                timestamp,
            )
        )

    return rows
