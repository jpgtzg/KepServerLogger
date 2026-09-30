"""
Shared config/settings singletons for the ingestor.
"""

from lib.config import IngestorConfig
from lib.settings import Settings

config = IngestorConfig()  # pyright: ignore[reportCallIssue]
settings = Settings.load()
