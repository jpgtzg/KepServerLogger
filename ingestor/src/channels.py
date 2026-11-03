"""
The tags each tag channel of a server subscribes to, read from the server's tag CSV.
"""

from lib.servers import ServerConfig
from lib.tag_extractor import extract_tags_from_csv

_EXCLUDE_TAGS = ["_Write", "_WRITE"]


def get_channel_tags(server: ServerConfig) -> dict[str, dict[str, str]]:
    """
    Returns channel -> {tag name: node id}. The tag name is the node id without the
    channel prefix, which is how a tag is stored in the database. A server with no
    `tag_channels` logs no tags.
    """
    channels: dict[str, dict[str, str]] = {}
    for channel, prefix in server.tag_channels.items():
        node_ids = extract_tags_from_csv(
            prefix=prefix,
            type_filter=channel,
            separator=server.csv_tag_separator,
            exclude_tags=_EXCLUDE_TAGS,
            tag_column=server.csv_tag_column_name,
            filename=server.csv_filename,
        )
        channels[channel] = {n.removeprefix(prefix + "."): n for n in node_ids}
    return channels
