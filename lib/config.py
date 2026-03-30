from enum import Enum
from pydantic_settings import BaseSettings


class MetricType(str, Enum):
    TAGS = "tags"
    CPU = "cpu"
    RAM = "ram"
    NETWORK = "network"
    SERVICES = "services"
    KEPSERVER_EVENTS = "kepserverevents"


class Config(BaseSettings):
    client_username: str
    client_password: str
    app_uri: str
    host_name: str
    application_name: str

    kepserver_server_url: str
    kepserver_username: str
    kepserver_password: str
    kepserver_event_log_url: str

    logging_metrics: list[MetricType]
    csv_tag_column_name: str
    csv_tag_separator: str

    log_retention_days: int
    log_cleanup_interval: int

    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    cert_path: str
    key_path: str

    timestamp_format: str

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


config = Config()
