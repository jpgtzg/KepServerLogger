import socket

from lib.models import Hostname
from lib.utils import utcnow


def get_hostname() -> Hostname:
    return Hostname(timestamp=utcnow(), host_name=socket.gethostname())
