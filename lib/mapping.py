"""
Maps the fields of the models to the OPC UA tag names.

Note: Prefixes are not included in the mapping, they are defined in the settings.json file
"""

from typing import Literal

CPUField = Literal["timestamp", "usage"]
RAMField = Literal["timestamp", "total_kb", "free_kb"]
NetworkField = Literal[
    "timestamp",
    "operational_status",
    "network_interface_type",
    "kb_bytes_sent",
    "kb_bytes_received",
]
ServiceField = Literal[
    "timestamp", "name", "status", "service_type", "machine_name", "process_ids"
]
EventField = Literal["timestamp", "name", "source", "message", "hash"]

CPU_FIELDS = list(CPUField.__args__)
RAM_FIELDS = list(RAMField.__args__)
NETWORK_FIELDS = list(NetworkField.__args__)
SERVICE_FIELDS = list(ServiceField.__args__)
EVENT_FIELDS = list(EventField.__args__)
