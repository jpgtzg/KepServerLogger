"""
This module defines the configuration models for the application
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

    db_host: str
    db_port: int
    db_user: str
    db_password: str

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


