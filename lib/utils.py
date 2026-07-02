from datetime import datetime, timezone

from lib.servers import ServerConfig
from lib.settings import MetricsConfig
from lib.tag_extractor import extract_tags_from_csv


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


_EXCLUDE_TAGS = ["_Write", "_WRITE"]


def get_tags(channel: str, server: ServerConfig, metrics_config: MetricsConfig) -> list[str]:
    return extract_tags_from_csv(
        prefix=metrics_config.tag_channels[channel],
        type_filter=channel,
        separator=server.csv_tag_separator,
        exclude_tags=_EXCLUDE_TAGS,
        tag_column=server.csv_tag_column_name,
        filename=server.csv_filename,
    )
