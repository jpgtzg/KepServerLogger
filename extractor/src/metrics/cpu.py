import psutil
from lib.models import CPUUsage
from lib.utils import utcnow

def get_total_cpu_usage() -> CPUUsage:
    return CPUUsage(timestamp=utcnow(), usage=float(psutil.cpu_percent(interval=1.0)))
