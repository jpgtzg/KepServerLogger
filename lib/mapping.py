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
