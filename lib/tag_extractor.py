"""
Generates a .json tag list from a .csv file
"""

from logging import getLogger

import pandas as pd

logger = getLogger(__name__)


def extract_tags_from_csv(
    prefix: str,
    type_filter: str,
    separator: str = ";",
    exclude_tags: list[str] = [],
    tag_column: str = "",
    type_column: str = "Type",
    filename: str = "",
) -> list[str]:
    """
    Extracts tags from a .csv file and returns a list of tags.

    Args:
        prefix: The OPC UA namespace prefix to prepend to each tag.
        type_filter: The value to filter on in the type_column. Required — determines which tag group to extract.
        separator: The separator to use to split the tags in the .csv file.
        exclude_tags: A list of strings to exclude from the tags.
        tag_column: The column name to extract the tags from in the .csv file.
        type_column: The column name used to filter by type.
        filename: The filename to read the tags from.

    Returns:
        A list of tags in the OPC UA namespace.
    """

    logger.info(f"Reading tags from {filename}...")

    df = pd.read_csv(filename, sep=separator)
    tags = df.loc[df[type_column] == type_filter, tag_column].dropna().tolist()

    if prefix:
        tags_json = [prefix + "." + tag.strip().removesuffix(".BAL") for tag in tags]
    else:
        tags_json = [tag.strip().removesuffix(".BAL") for tag in tags]

    tags_json: list[str] = [
        tag for tag in tags_json if not any(exclude in tag for exclude in exclude_tags)
    ]

    logger.info(f"Tags extracted successfully! {len(tags_json)} tags found")
    return tags_json
