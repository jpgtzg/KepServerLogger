"""
This module contains the models for the data that is ingested into the database.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, field_validator

from lib.settings import settings


class OPCUAModel(BaseModel):
    timestamp: datetime

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v: str | datetime) -> datetime:
        if isinstance(v, datetime):
            return (
                v.astimezone(timezone.utc)
                if v.tzinfo
                else v.replace(tzinfo=timezone.utc)
            )
        try:
            # Primary format configured for OPC UA payloads (default ends with 'Z').
            dt = datetime.strptime(v, settings.timestamp_format)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            # Accept ISO-8601 with optional milliseconds and optional Z/offset.
            # Examples observed from KepServer event log:
            # - 2026-04-08T16:03:49.541
            # - 2026-04-08T16:03:49.541Z
            # - 2026-04-08T16:03:49+00:00
            try:
                iso = v.replace("Z", "+00:00")
                dt = datetime.fromisoformat(iso)
                return (
                    dt.astimezone(timezone.utc)
                    if dt.tzinfo
                    else dt.replace(tzinfo=timezone.utc)
                )
            except Exception as e:
                raise ValueError(f"Could not parse timestamp '{v}': {e}")

    def to_opcua(self, timestamp_format: str) -> dict:
        data = self.model_dump()
        ts = (
            self.timestamp.astimezone(timezone.utc)
            if self.timestamp.tzinfo
            else self.timestamp.replace(tzinfo=timezone.utc)
        )
        data["timestamp"] = ts.strftime(timestamp_format)
        return data


class TagData(BaseModel):
    tag: str
    value: str
    status_code: str
    source_timestamp: datetime | None
    server_timestamp: datetime


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

    @field_validator("process_ids", mode="before")
    @classmethod
    def parse_process_ids(cls, v):
        if isinstance(v, str):
            return [int(pid) for pid in v.split(",") if pid]
        return v

    def to_opcua(self, timestamp_format: str) -> dict:
        data = super().to_opcua(timestamp_format)
        data["process_ids"] = ",".join(str(pid) for pid in self.process_ids)
        return data


class KepEvent(OPCUAModel):
    name: str
    source: str
    message: str
    hash: str


class OpcConnectionEvent(OPCUAModel):
    client_name: str
    kind: str
    reason: str
    hash: str
