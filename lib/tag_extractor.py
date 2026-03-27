"""
Generates a .json tag list from a .csv file
"""

import pandas as pd

TAG_PREFIX = "ns=2;s="

def extract_tags(
    use_prefix: bool = True,
    separator: str = ";",
    exclude_tags: list[str] = [],
    tag_column: str = "",
    filename: str = "",
) -> dict:
    """
    Extracts tags from a .csv file and returns a list of tags.

    Args:
        use_prefix: Whether to use the prefix of the tags in the OPC UA namespace, will be prepended to the tags. If not provided, the tags will be returned without the prefix.
        separator: The separator to use to split the tags in the .csv file.
        exclude_tags: A list of strings to exclude from the tags. The tags will be excluded if they contain any of the strings in the list.
        tag_column: The column name to extract the tags from in the .csv file.
        filename: The filename to read the tags from in the .csv file.

    Returns:
        A list of tags in the OPC UA namespace.
    """

    print(f"Reading tags from {filename}...")

    df = pd.read_csv(filename, sep=separator)
    tags = df[tag_column].dropna().tolist()

    if use_prefix:
        tags_json = [TAG_PREFIX + tag.strip().removesuffix(".BAL") for tag in tags]
    else:
        tags_json = [tag.strip().removesuffix(".BAL") for tag in tags]

    tags_json = [
        tag for tag in tags_json if not any(exclude in tag for exclude in exclude_tags)
    ]

    print(f"Tags extracted successfully! {len(tags_json)} tags found")
    return tags_json
