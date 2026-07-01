"""
This module defines the configuration and settings models for the application
"""

from pydantic_settings import BaseSettings

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
