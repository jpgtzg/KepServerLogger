from __future__ import annotations

import psutil


def get_network_interfaces() -> list[dict[str, object]]:
    counters = psutil.net_io_counters(pernic=True)
    stats = psutil.net_if_stats()
    interfaces: list[dict[str, object]] = []

    for name, io in counters.items():
        interface_stat = stats.get(name)
        is_up = bool(interface_stat.isup) if interface_stat else False
        speed = int(interface_stat.speed) if interface_stat and interface_stat.speed is not None else 0
        ni_type = "Ethernet" if speed > 0 else "Unknown"

        interfaces.append(
            {
                "interface": name,
                "operational_status": "Up" if is_up else "Down",
                "network_interface_type": ni_type,
                "kb_bytes_sent": float(io.bytes_sent / 1024.0),
                "kb_bytes_received": float(io.bytes_recv / 1024.0),
            }
        )

    return interfaces
