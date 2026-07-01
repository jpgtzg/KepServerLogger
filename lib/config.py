"""
This module defines the configuration and settings models for the application
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings

## --------- Settings Model --------- ##


class MetricType(str, Enum):
    """
    Options for metrics to log
    """

    TAG_CHANNELS = "tag_channels"
    CPU = "cpu"
    RAM = "ram"
    NETWORK = "network"
    SERVICES = "services"
    KEPSERVER_EVENTS = "kepserverevents"
    OPC_DIAGNOSTICS = "opcdiagnostics"


class PrefixConfig(BaseModel):
    prefix: str


class OpcDiagnosticsConfig(PrefixConfig):
    log_path: str


class ServiceConfig(BaseModel):
    prefix: str
    names: list[str]


class MetricsConfig(BaseModel):
    """
    Configuration for all metrics
    """

    cpu: PrefixConfig
    ram: PrefixConfig
    network: PrefixConfig
    services: ServiceConfig
    kepserverevents: PrefixConfig
    tag_channels: dict[str, str]
    opcdiagnostics: OpcDiagnosticsConfig
    host_name: PrefixConfig


class Settings(BaseModel):
    """
    Settings for the application, read from the settings.json file
    """

    timestamp_format: str
    log_retention_days: int
    polling_interval_seconds: int = 1
    metrics_to_log: list[MetricType]
    metrics_config: MetricsConfig

    @classmethod
    def load(cls, path: str = "settings.json") -> Settings:
        return cls.model_validate(json.loads(Path(path).read_text()))


## --------- Config Model --------- ##


class Config(BaseSettings):
    """
    Configuration for the application, read from the .env file
    """

    app_uri: str
    host_name: str
    application_name: str

    kepserver_server_url: str
    kepserver_username: str
    kepserver_password: str
    kepserver_event_log_url: str

    csv_tag_column_name: str
    csv_tag_opcua_path: str
    csv_tag_separator: str
    csv_filename: str

    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    cert_path: str
    key_path: str

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


## --------- Singleton Instances --------- ##

config = Config()
settings = Settings.load()
