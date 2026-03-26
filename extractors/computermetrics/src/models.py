from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ServiceInfo:
    name: str
    status: str
    service_type: str
    machine_name: str
    process_ids: list[int]


@dataclass
class KepEvent:
    timestamp: str
    name: str
    source: str
    message: str
    hash: str

