"""
Generates a .json tag list from a .csv file
"""

import pandas as pd


def extract_tags(
    prefix: str,
    separator: str = ";",
    exclude_tags: list[str] = [],
    tag_column: str = "",
    filename: str = "",
) -> dict:
    """
    Extracts tags from a .csv file and returns a list of tags.

    Args:
        prefix: The prefix of the tags in the OPC UA namespace.
        separator: The separator to use to split the tags in the .csv file.
        exclude_tags: A list of strings to exclude from the tags. The tags will be excluded if they contain any of the strings in the list.
        tag_column: The column name to extract the tags from in the .csv file.
        filename: The filename to read the tags from in the .csv file.

    Returns:
        A list of tags in the OPC UA namespace.
    """

    print(f"Reading tags from {filename}...")

    prefix = f"ns=2;s={prefix}."

    df = pd.read_csv(filename, sep=separator)
    tags = df[tag_column].dropna().tolist()

    tags_json = [prefix + tag.strip().removesuffix(".BAL") for tag in tags]

    tags_json = [
        tag for tag in tags_json if not any(exclude in tag for exclude in exclude_tags)
    ]

    print(f"Tags extracted successfully! {len(tags_json)} tags found")
    return tags_json
