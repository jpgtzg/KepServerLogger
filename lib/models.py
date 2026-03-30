"""
This module contains the models for the data that is ingested into the database.
"""

from pydantic import BaseModel
from datetime import datetime

class Tag(BaseModel):
    tag: str
    value: str
    status_code: str
    source_timestamp: datetime
    server_timestamp: datetime


class CPUUsage(BaseModel):
    timestamp: datetime
    usage: float


class RAMUsage(BaseModel):
    timestamp: datetime
    total_kb: int
    free_kb: int


class NetworkUsage(BaseModel):
    timestamp: datetime
    interface: str
    operational_status: str
    network_interface_type: str
    kb_bytes_sent: float
    kb_bytes_received: float


class ServiceInfo(BaseModel):
    timestamp: datetime
    name: str
    status: str
    service_type: str
    machine_name: str
    process_ids: list[int]


class KepEvent(BaseModel):
    timestamp: datetime
    name: str
    source: str
    message: str
    hash: str
