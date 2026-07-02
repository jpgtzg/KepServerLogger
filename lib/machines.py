"""
This module defines the machine configuration models for the application.
"""

import json
from pydantic import BaseModel
from pathlib import Path

class MachineConfig(BaseModel):
    """
    Configuration for a machine, read from the machines.json file
    """

    name: str
    ip_address: str
    port: int
    username: str
    password: str
    cert_path: str
    key_path: str

class MachinesConfig(BaseModel)
    """
    Configuration for all machines, read from the machines.json file
    """

    machines: list[MachineConfig]

    @classmethod
    def load(cls, path: str = "machines.json") -> "MachinesConfig":
        return cls.model_validate(json.loads(Path(path).read_text()))

machines_config = MachinesConfig.load()
