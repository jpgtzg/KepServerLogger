import psutil
from lib.models import RAMUsage
from lib.utils import utcnow


def get_memory_info() -> RAMUsage:
    memory = psutil.virtual_memory()
    total_kb = int(memory.total // 1024)
    free_kb = int(memory.available // 1024)
    return RAMUsage(timestamp=utcnow(), total_kb=total_kb, free_kb=free_kb)
