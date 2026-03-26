from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class MetricType(str, Enum):
    CPU = "cpu"
    RAM = "ram"
    NETWORK = "network"
    SERVICES = "services"
    KEPSERVER_EVENTS = "kepserverevents"


@dataclass(frozen=True)
class AppConfig:
    read_interval_ms: int
    logging_metrics: list[MetricType]
    service_names: list[str]


def load_config(settings_path: str | Path = "settings.json") -> AppConfig:
    path = Path(settings_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    read_interval = int(payload.get("read_interval", 1000))
    raw_metrics = payload.get("logging", [])
    raw_services = payload.get("services", [])

    metric_map = {m.value: m for m in MetricType}
    metrics: list[MetricType] = []
    for metric_name in raw_metrics:
        key = str(metric_name).strip().lower()
        if key not in metric_map:
            raise ValueError(f"Unknown metric type: {metric_name}")
        metrics.append(metric_map[key])

    services = [str(name) for name in raw_services]
    return AppConfig(
        read_interval_ms=read_interval,
        logging_metrics=metrics,
        service_names=services,
    )
