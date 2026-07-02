"""
This module defines the machine configuration models for the application.
"""

import json
from pathlib import Path

from pydantic import BaseModel


class ServerConfig(BaseModel):
    """
    Configuration for a machine, read from the machines.json file
    """

    name: str
    url: str
    username: str
    password: str
    db_name: str
    cert_path: str
    key_path: str

    csv_tag_column_name: str
    csv_tag_separator: str
    csv_filename: str



def load_servers_configs(path: str = "servers.json") -> list[ServerConfig]:
    return [ServerConfig.model_validate(s) for s in json.loads(Path(path).read_text())]
