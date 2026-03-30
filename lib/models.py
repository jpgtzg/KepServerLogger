"""
This module contains the models for the data that is ingested into the database.
"""

from __future__ import annotations
from pydantic import BaseModel


class Tag(BaseModel):
    tag: str
    value: str
    status_code: str
    source_timestamp: str
    server_timestamp: str


class CPUUsage(BaseModel):
    timestamp: str
    usage: float


class RAMUsage(BaseModel):
    timestamp: str
    total_kb: int
    free_kb: int


class NetworkUsage(BaseModel):
    timestamp: str
    interface: str
    operational_status: str
    network_interface_type: str
    kb_bytes_sent: float
    kb_bytes_received: float


class ServiceInfo(BaseModel):
    timestamp: str
    name: str
    status: str
    service_type: str
    machine_name: str
    process_ids: list[int]


class KepEvent(BaseModel):
    timestamp: str
    name: str
    source: str
    message: str
    hash: str
