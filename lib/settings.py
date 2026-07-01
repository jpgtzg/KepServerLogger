"""
This module contains the settings for the application, read from the settings.json file.
"""

import json
from enum import Enum
from pathlib import Path

from pydantic import BaseModel


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


settings = Settings.load()
