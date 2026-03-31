from __future__ import annotations

from enum import Enum
from pydantic_settings import BaseSettings
from pydantic import BaseModel
from pathlib import Path
import json

## --------- Settings Model --------- ##


class MetricType(str, Enum):
    """
    Options for metrics to log
    """

    PLC_TAGS = "plc_tags"
    CPU = "cpu"
    RAM = "ram"
    NETWORK = "network"
    SERVICES = "services"
    KEPSERVER_EVENTS = "kepserverevents"


class ServiceConfig(BaseModel):
    """
    Configuration for services
    """

    prefix: str
    names: list[str]


class MetricsConfig(BaseModel):
    """
    Configuration for all metrics
    """

    cpu: str
    ram: str
    network: str
    services: ServiceConfig
    kepserverevents: str
    plc_tags: str


class Settings(BaseModel):
    """
    Settings for the application, read from the settings.json file
    """

    timestamp_format: str
    log_retention_days: int
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

    client_username: str
    client_password: str

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


config = Config()
