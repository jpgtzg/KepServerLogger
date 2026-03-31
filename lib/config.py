from enum import Enum
from pydantic_settings import BaseSettings


class MetricType(str, Enum):
    PLC_TAGS = "plc_tags"
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
