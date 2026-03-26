from __future__ import annotations

import platform

import win32service

from models import ServiceInfo


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


def get_service_info(service_name: str) -> ServiceInfo:
    scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
    try:
        service_handle = win32service.OpenService(
            scm,
            service_name,
            win32service.SERVICE_QUERY_STATUS,
        )
        try:
            status = win32service.QueryServiceStatus(service_handle)
            process_info = win32service.QueryServiceStatusEx(service_handle)

            current_state = int(status[1])
            service_type = int(status[0])
            process_id = int(process_info.get("ProcessId", 0))

            # Preserve current behavior where stopped services have no PID.
            process_ids = [process_id] if process_id else []

            return ServiceInfo(
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
