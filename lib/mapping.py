"""
Maps the fields of the models to the OPC UA tag names.

Note: Prefixes are not included in the mapping, they are defined in the settings.json file

TODO : CHECK IF THIS IS NEEDED
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

CPU_FIELDS = [CPUField.timestamp, CPUField.usage]
RAM_FIELDS = [RAMField.timestamp, RAMField.total_kb, RAMField.free_kb]
NETWORK_FIELDS = [NetworkField.timestamp, NetworkField.operational_status, NetworkField.network_interface_type, NetworkField.kb_bytes_sent, NetworkField.kb_bytes_received]
SERVICE_FIELDS = [ServiceField.timestamp, ServiceField.name, ServiceField.status, ServiceField.service_type, ServiceField.machine_name, ServiceField.process_ids]
EVENT_FIELDS = [EventField.timestamp, EventField.name, EventField.source, EventField.message, EventField.hash]