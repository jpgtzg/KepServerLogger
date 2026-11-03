"""
Settings read from settings.json, shared by the extractor and the ingestor.

Each side loads its own subclass and ignores the other side's keys, so the same
file layout works for both without placeholders.
"""

import json
from pathlib import Path

from pydantic import BaseModel, field_validator

from lib.metrics import METRICS


class Settings(BaseModel):
    polling_interval_seconds: int = 1
    node_prefix: str = "ns=2;s=IDL.Metrics"
    metrics: list[str] = list(METRICS)

    @field_validator("metrics")
    @classmethod
    def known_metrics(cls, names: list[str]) -> list[str]:
        unknown = sorted(set(names) - set(METRICS))
        if unknown:
            raise ValueError(
                f"unknown metrics: {', '.join(unknown)} (known: {', '.join(METRICS)})"
            )
        return names

    @property
    def host_name_node(self) -> str:
        return f"{self.node_prefix}.host_name"

    @classmethod
    def load(cls, path: str = "settings.json"):
        return cls.model_validate(json.loads(Path(path).read_text()))


class ExtractorSettings(Settings):
    # Windows services whose state is reported.
    services: list[str] = []


class IngestorSettings(Settings):
    log_retention_days: int
