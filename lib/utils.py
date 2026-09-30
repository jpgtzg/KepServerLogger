from datetime import datetime, timezone

from lib.servers import ServerConfig
from lib.settings import MetricsConfig, MetricType, Settings
from lib.tag_extractor import extract_tags_from_csv

TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
RECONNECT_DELAY = 5
MAX_CONSECUTIVE_METRIC_FAILURES = 3
OPCUA_REQUEST_TIMEOUT_SECONDS = 30

_EXCLUDE_TAGS = ["_Write", "_WRITE"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_tags(
    channel: str, server: ServerConfig, metrics_config: MetricsConfig
) -> list[str]:
    assert metrics_config.tag_channels is not None
    server_channels = metrics_config.tag_channels[server.name]
    return extract_tags_from_csv(
        prefix=server_channels[channel],
        type_filter=channel,
        separator=server.csv_tag_separator,
        exclude_tags=_EXCLUDE_TAGS,
        tag_column=server.csv_tag_column_name,
        filename=server.csv_filename,
    )


def get_server_channels(
    server: ServerConfig, metrics_config: MetricsConfig
) -> dict[str, str] | None:
    """
    Gets all the tag channels for the given server. Returns a dictionary mapping channel names to node prefixes.
    """
    if not metrics_config.tag_channels:
        return None
    return metrics_config.tag_channels.get(server.name)


def get_channel_tags(server: ServerConfig, settings: Settings) -> dict[str, list[str]]:
    """
    Gets the tags for each channel of the given server.
    """
    server_channels = get_server_channels(server, settings.metrics_config)
    if (
        MetricType.TAG_CHANNELS not in settings.metrics_to_log
        or server_channels is None
    ):
        return {}
    return {
        channel: get_tags(channel, server, settings.metrics_config)
        for channel in server_channels
    }
