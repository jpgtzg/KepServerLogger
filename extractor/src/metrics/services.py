import platform

import win32service  # Note: this is a Windows-only module  # pyright: ignore[reportMissingModuleSource]

from lib.models import ServiceInfo
from lib.utils import utcnow


SERVICE_STATE_MAP = {
    win32service.SERVICE_STOPPED: "Stopped",
    win32service.SERVICE_START_PENDING: "StartPending",
    win32service.SERVICE_STOP_PENDING: "StopPending",
    win32service.SERVICE_RUNNING: "Running",
    win32service.SERVICE_CONTINUE_PENDING: "ContinuePending",
    win32service.SERVICE_PAUSE_PENDING: "PausePending",
    win32service.SERVICE_PAUSED: "Paused",
}


SERVICE_TYPE_FLAGS = (
    (win32service.SERVICE_KERNEL_DRIVER, "KernelDriver"),
    (win32service.SERVICE_FILE_SYSTEM_DRIVER, "FileSystemDriver"),
    (win32service.SERVICE_WIN32_OWN_PROCESS, "Win32OwnProcess"),
    (win32service.SERVICE_WIN32_SHARE_PROCESS, "Win32ShareProcess"),
    (win32service.SERVICE_INTERACTIVE_PROCESS, "InteractiveProcess"),
)


def _service_type_to_string(service_type: int) -> str:
    parts = [name for bitmask, name in SERVICE_TYPE_FLAGS if service_type & bitmask]
    return "|".join(parts) if parts else str(service_type)


def _resolve_service_name(name_or_display_name: str) -> str:
    """
    win32service.OpenService expects the *service name* (key name), not display name.
    Uses GetServiceKeyName to directly map a display name to its service key name.
    """
    scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
    try:
        return win32service.GetServiceKeyName(scm, name_or_display_name)
    except win32service.error:
        return name_or_display_name
    finally:
        win32service.CloseServiceHandle(scm)


def get_service_info(service_name: str) -> ServiceInfo:
    scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
    try:
        open_name = service_name
        try:
            service_handle = win32service.OpenService(
                scm,
                open_name,
                win32service.SERVICE_QUERY_STATUS,
            )
        except win32service.error as exc:
            # WinError 1060: service does not exist as an installed service.
            if getattr(exc, "winerror", None) == 1060:
                open_name = _resolve_service_name(service_name)
                service_handle = win32service.OpenService(
                    scm,
                    open_name,
                    win32service.SERVICE_QUERY_STATUS,
                )
            else:
                raise
        try:
            status = win32service.QueryServiceStatus(service_handle)
            process_info = win32service.QueryServiceStatusEx(service_handle)

            current_state = int(status[1])
            service_type = int(status[0])
            process_id = int(process_info.get("ProcessId", 0))

            # Preserve current behavior where stopped services have no PID.
            process_ids = [process_id] if process_id else []

            return ServiceInfo(
                timestamp=utcnow(),
                name=service_name,
                status=SERVICE_STATE_MAP.get(current_state, str(current_state)),
                service_type=_service_type_to_string(service_type),
                machine_name=platform.node(),
                process_ids=process_ids,
            )
        finally:
            win32service.CloseServiceHandle(service_handle)
    except Exception as exc:
        raise RuntimeError(f"Error retrieving service '{service_name}': {exc}") from exc
    finally:
        win32service.CloseServiceHandle(scm)
