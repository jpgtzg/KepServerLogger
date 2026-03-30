import psutil

def get_total_cpu_usage() -> float:
    return float(psutil.cpu_percent(interval=1.0))
