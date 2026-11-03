"""
Every metric the extractor publishes and the ingestor stores, described once.

A metric travels as a JSON-encoded list of models in one string node,
`<node_prefix>.<node>.batch`. A scalar metric (cpu, ram, storage) is a list of one,
so every metric has the same wire format and the same code path on both sides.

To add a metric: a model in `lib/models.py`, one `Metric` below, a getter in the
extractor, and a table in the ingestor's schema.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field

from asyncua import ua

from lib.models import (
    CPUUsage,
    KepEvent,
    NetworkUsage,
    OPCUAModel,
    RAMUsage,
    ServiceInfo,
    StorageUsage,
)
from lib.subscription import SubscriptionConfig


@dataclass(frozen=True)
class Metric:
    name: str
    node_name: str
    model: type[OPCUAModel]
    table_name: str
    config: SubscriptionConfig = SubscriptionConfig()
    columns: dict[str, str] = field(default_factory=dict)
    idempotent: bool = False

    def node_id(self, node_prefix: str) -> str:
        return f"{node_prefix}.{self.node_name}.batch"

    def encode(self, models: Sequence[OPCUAModel]) -> str:
        """Extractor side: the string written to the node."""
        return json.dumps([m.to_opcua() for m in models])

    def decode(self, data_value: ua.DataValue) -> list[OPCUAModel]:
        """
        Ingestor side: the models carried by one data change. Raises ValueError when
        the node reports a bad status or holds something that is not the expected JSON.
        """
        status = data_value.StatusCode
        if status is not None and not status.is_good():
            raise ValueError(f"{self.name}: bad status {status.name}")
        if data_value.Value is None:
            return []
        raw = data_value.Value.Value
        if not raw:
            return []
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"{self.name}: invalid JSON ({e}); starts with {str(raw)[:80]!r}"
            ) from e
        return [self.model(**item) for item in payload]


METRICS: dict[str, Metric] = {
    m.name: m
    for m in [
        Metric("cpu", "CPU", CPUUsage, "cpu_usage"),
        Metric("ram", "RAM", RAMUsage, "ram_usage"),
        Metric("storage", "Storage", StorageUsage, "storage_usage"),
        Metric("network", "Network", NetworkUsage, "network_usage"),
        Metric("services", "Services", ServiceInfo, "services"),
        Metric(
            "events",
            "Events",
            KepEvent,
            "events",
            columns={"name": "event_name"},
            idempotent=True,
        ),
    ]
}
