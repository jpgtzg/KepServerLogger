"""
Shared config/settings singletons for the ingestor.
"""

from lib.config import IngestorConfig
from lib.settings import IngestorSettings

config = IngestorConfig()  # pyright: ignore[reportCallIssue]
settings = IngestorSettings.load()
