"""
This module contains the models for the data that is ingested into the database.
"""

from pydantic import BaseModel
from datetime import datetime


class OPCUAModel(BaseModel):
    timestamp: datetime

    def to_opcua(self, timestamp_format: str) -> dict:
        data = self.model_dump()
        data["timestamp"] = self.timestamp.strftime(timestamp_format)
        return data


class CPUUsage(OPCUAModel):
    usage: float


class RAMUsage(OPCUAModel):
    total_kb: int
    free_kb: int


class NetworkUsage(OPCUAModel):
    interface: str
    operational_status: str
    network_interface_type: str
    kb_bytes_sent: float
    kb_bytes_received: float


class ServiceInfo(OPCUAModel):
    name: str
    status: str
    service_type: str
    machine_name: str
    process_ids: list[int]

    def to_opcua(self, timestamp_format: str) -> dict:
        data = super().to_opcua(timestamp_format)
        data["process_ids"] = ",".join(str(pid) for pid in self.process_ids)
        return data


class KepEvent(OPCUAModel):
    name: str
    source: str
    message: str
    hash: str
