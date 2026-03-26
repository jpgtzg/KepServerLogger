from __future__ import annotations

import psutil


def get_total_cpu_usage() -> float:
    # Match .NET behavior: sample after a short warm-up interval.
    return float(psutil.cpu_percent(interval=1.0))
