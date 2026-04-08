import psutil
from lib.models import NetworkUsage
from lib.utils import utcnow


def get_network_interfaces() -> list[NetworkUsage]:
    stats = psutil.net_if_stats()
    counters = psutil.net_io_counters(pernic=True)
    interfaces: list[NetworkUsage] = []

    for name, stat in stats.items():
        io = counters.get(name)
        interfaces.append(
            NetworkUsage(
                timestamp=utcnow(),
                interface=name,
                operational_status="Up" if stat.isup else "Down",
                network_interface_type="Ethernet" if stat.speed > 0 else "Unknown",
                kb_bytes_sent=float(io.bytes_sent / 1024.0) if io else 0.0,
                kb_bytes_received=float(io.bytes_recv / 1024.0) if io else 0.0,
            )
        )

    return interfaces
