"""
This module defines the configuration models for the application
"""

import socket

from pydantic_settings import BaseSettings

## --------- Config Model --------- ##


class Config(BaseSettings):
    """
    Configuration for the application, read from the .env file
    """

    application_name: str

    @property
    def app_uri(self) -> str:
        return f"urn:{socket.gethostname()}:{self.application_name}"

    db_host: str
    db_port: int
    db_user: str
    db_password: str

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


