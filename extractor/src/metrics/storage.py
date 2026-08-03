import psutil
from lib.models import StorageUsage
from lib.utils import utcnow


def get_storage():
    usage = psutil.disk_usage("C:\\")
    free_gb = usage.free / (1024**3)
    used_gb = usage.used / (1024**3)
    total_gb = usage.total / (1024**3)

    return StorageUsage(
        timestamp=utcnow(), free_gb=free_gb, used_gb=used_gb, total_gb=total_gb
    )
