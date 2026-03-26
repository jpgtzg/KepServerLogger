from dotenv import load_dotenv
from dataclasses import dataclass
import os

load_dotenv()


@dataclass(frozen=True)
class Config:
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
    csv_tag_prefix: str
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

    @classmethod
    def load(cls) -> "Config":
        return cls(
            client_username=os.getenv("CLIENT_USERNAME"),
            client_password=os.getenv("CLIENT_PASSWORD"),
            
            app_uri=os.getenv("APP_URI"),
            host_name=os.getenv("HOST_NAME"),
            application_name=os.getenv("APPLICATION_NAME"),
            
            kepserver_server_url=os.getenv("KEPSERVER_SERVER_URL"),
            kepserver_username=os.getenv("KEPSERVER_USERNAME"),
            kepserver_password=os.getenv("KEPSERVER_PASSWORD"),
            kepserver_event_log_url=os.getenv("KEPSERVER_EVENT_LOG_URL"),
            
            csv_tag_column_name=os.getenv("CSV_TAG_COLUMN_NAME"),
            csv_tag_prefix=os.getenv("CSV_TAG_PREFIX"),
            csv_tag_separator=os.getenv("CSV_TAG_SEPARATOR"),

            log_retention_days=os.getenv("LOG_RETENTION_DAYS"),
            log_cleanup_interval=os.getenv("LOG_CLEANUP_INTERVAL"),

            db_host=os.getenv("DB_HOST"),
            db_port=os.getenv("DB_PORT"),
            db_name=os.getenv("DB_NAME"),
            db_user=os.getenv("DB_USER"),
            db_password=os.getenv("DB_PASSWORD"),

            cert_path=os.getenv("CERT_PATH"),
            key_path=os.getenv("KEY_PATH"),

            timestamp_format=os.getenv("TIMESTAMP_FORMAT"),
        )