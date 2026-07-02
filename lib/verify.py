"""
Run this once to get a list of all nodes that need to be created in KepServer.
"""

from logging import getLogger

from lib.config import config
from lib.settings import settings
from lib.tag_extractor import extract_tags_from_csv

logger = getLogger(__name__)

_EXCLUDE_TAGS = ["_Write", "_WRITE"]


def get_tags(channel: str) -> list[str]:
    prefix = settings.metrics_config.tag_channels[channel]
    return extract_tags_from_csv(
        prefix=prefix,
        type_filter=channel,
        separator=config.csv_tag_separator,
        exclude_tags=_EXCLUDE_TAGS,
        tag_column=config.csv_tag_column_name,
        filename=config.csv_filename,
    )
