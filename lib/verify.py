"""
Run this once to get a list of all nodes that need to be created in KepServer.
"""

from logging import getLogger

from lib.config import MetricType, config, settings
from lib.tag_extractor import extract_tags_from_csv

logger = getLogger(__name__)


def get_tags(metric_type: MetricType) -> list[str]:
    prefix_config = getattr(settings.metrics_config, metric_type.value)
    exclude_tags = ["_Write", "_WRITE"] if metric_type == MetricType.PLC_TAGS else []
    return extract_tags_from_csv(
        prefix=prefix_config.prefix,
        type_filter=metric_type.value,
        separator=config.csv_tag_separator,
        exclude_tags=exclude_tags,
        tag_column=config.csv_tag_column_name,
        filename=config.csv_filename,
    )
