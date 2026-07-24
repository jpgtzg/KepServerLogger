"""
Shared config/settings singletons for the extractor.

Kept in a dedicated module (rather than instantiated in main.py) so that
metrics/events.py and publishers/opcua.py can import them without a
circular import on main.py.
"""

from lib.config import ExtractorConfig
from lib.settings import Settings

config = ExtractorConfig()  # pyright: ignore[reportCallIssue]
settings = Settings.load()
