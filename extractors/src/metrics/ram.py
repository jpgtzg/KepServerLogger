from __future__ import annotations

import psutil


def get_memory_info() -> tuple[int, int]:
    memory = psutil.virtual_memory()
    total_kb = int(memory.total // 1024)
    free_kb = int(memory.available // 1024)
    return total_kb, free_kb
