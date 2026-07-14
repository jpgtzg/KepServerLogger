"""
This module contains the settings for the application, read from the settings.json file.
"""

import json
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, model_validator


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

    cpu: Optional[PrefixConfig] = None
    ram: Optional[PrefixConfig] = None
    network: Optional[PrefixConfig] = None
    services: Optional[ServiceConfig] = None
    kepserverevents: Optional[PrefixConfig] = None
    tag_channels: Optional[dict[str, dict[str, str]]] = None
    opcdiagnostics: Optional[OpcDiagnosticsConfig] = None
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

    @model_validator(mode="after")
    def check_metric_configs(self) -> "Settings":
        missing = [
            m.value
            for m in self.metrics_to_log
            if getattr(self.metrics_config, m.value) is None
        ]
        if missing:
            raise ValueError(
                f"metrics_config entries missing for enabled metrics: {', '.join(missing)}"
            )
        return self

    @classmethod
    def load(cls, path: str = "settings.json") -> "Settings":
        return cls.model_validate(json.loads(Path(path).read_text()))


