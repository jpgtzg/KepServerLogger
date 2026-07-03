"""
This module defines the configuration models for the application
"""

import socket
import sys
from pathlib import Path

from pydantic_settings import BaseSettings

## --------- Env file resolution --------- ##


def _env_file_path() -> Path:
    """
    Directory where the .env file should live.
    - In a PyInstaller .exe: alongside the executable
    - In source: current working directory
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "executable"):
        return Path(sys.executable).resolve().parent / ".env"
    return Path(".env")


## --------- Ingestor Config Model --------- ##


class IngestorConfig(BaseSettings):
    """
    Configuration for the ingestor, read from the .env file
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


## --------- Extractor Config Model --------- ##


class ExtractorConfig(BaseSettings):
    """
    Configuration for the extractor, read from the .env file deployed
    alongside the executable
    """

    application_name: str
    kepserver_server_url: str
    kepserver_username: str
    kepserver_password: str
    kepserver_event_log_url: str
    cert_path: str
    key_path: str

    @property
    def app_uri(self) -> str:
        return f"urn:{socket.gethostname()}:{self.application_name}"

    model_config = {
        "env_file": _env_file_path(),
        "env_file_encoding": "utf-8",
    }
