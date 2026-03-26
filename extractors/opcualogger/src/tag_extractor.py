"""
Generates a .json tag list from a .csv file
"""

import pandas as pd
from dotenv import load_dotenv
import os
import json

load_dotenv()

FILENAME = "TagList.csv"
TAG_COLUMN = os.getenv("TAG_COLUMN_NAME")

PREFIX = f"ns=2;s={os.getenv("PREFIX")}."

EXCLUDE_TAGS = ['_Write', '_WRITE']

SEPARATOR = os.getenv("SEPARATOR", ";")

def extract_tags(save_to_file : bool = False) -> dict:
    print(f"Reading tags from {FILENAME}...")

    df = pd.read_csv(FILENAME, sep=SEPARATOR)
    tags = df[TAG_COLUMN].dropna().tolist()
    
    tags_json = [PREFIX + tag.strip().removesuffix('.BAL') for tag in tags]

    tags_json = [tag for tag in tags_json if not any(exclude in tag for exclude in EXCLUDE_TAGS)]

    if save_to_file:
        with open("tags.json", "w") as f:
            json.dump(tags_json, f)
        print(f"Tags written to tags.json")
    
    print(f"Tags extracted successfully! {len(tags_json)} tags found")
    return tags_json
