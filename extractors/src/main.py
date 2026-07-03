import asyncio
import logging
import os
import time
from concurrent.futures import CancelledError
from typing import Optional

from asyncua.ua.uaerrors import UaError
from lib.logging import config_logging
from lib.opcua_client import OPCUAClient
from lib.settings import MetricType

from src.metrics import (
    get_memory_info,
    get_network_interfaces,
    get_service_info,
    get_total_cpu_usage,
)
from src.metrics.events import get_kepserver_events
from src.metrics.host_name import get_hostname
from src.metrics.opc_diagnostics import OpcDiagnosticsReader
from src.publishers.opcua import (
    publish_cpu_usage,
    publish_host_name,
    publish_kep_event,
    publish_network_usage,
    publish_opc_connection_events,
    publish_ram_usage,
    publish_service_info,
)
from src.state import config, settings

config_logging()
logger = logging.getLogger(__name__)

_RECONNECT_ERRORS = (ConnectionError, CancelledError, UaError)
_RECONNECT_DELAY = 5

# In frozen executables (e.g. PyInstaller) asyncua can be imported twice,
# producing two distinct UaError class objects. isinstance() then returns False
# for the "wrong" copy. Checking the MRO by name catches both copies.
_RECONNECT_CLASS_NAMES = frozenset(cls.__name__ for cls in _RECONNECT_ERRORS)


def _is_reconnect_error(exc: BaseException) -> bool:
    return isinstance(exc, _RECONNECT_ERRORS) or any(
        c.__name__ in _RECONNECT_CLASS_NAMES for c in type(exc).__mro__
    )


async def main() -> None:
    logger.info("Starting metrics extractor...")

    opcdiagnostics_config = settings.metrics_config.opcdiagnostics
    opc_reader: Optional[OpcDiagnosticsReader] = (
        OpcDiagnosticsReader(opcdiagnostics_config.log_path)
        if MetricType.OPC_DIAGNOSTICS in settings.metrics_to_log
        and opcdiagnostics_config is not None
        else None
    )

    try:
        while True:
            await _run_session(opc_reader)
    except KeyboardInterrupt:
        logger.info("Stopping logger...")
    finally:
        if opc_reader:
            opc_reader.close()


async def _run_session(opc_reader: Optional[OpcDiagnosticsReader]) -> None:
    logger.info(f"Connecting to {config.kepserver_server_url}...")

    client = OPCUAClient(
        url=config.kepserver_server_url,
        app_uri=config.app_uri,
        name=config.application_name,
        cert_path=config.cert_path,
        key_path=config.key_path,
        username=config.kepserver_username,
        password=config.kepserver_password,
    )

    await client.setup()

    logger.info("Initialization complete, starting main loop...")
    time.sleep(5)

    start_time = time.time()
    try:
        async with client:
            logger.info("OPC UA client connected, starting main loop")
            while True:
                if MetricType.CPU in settings.metrics_to_log:
                    try:
                        await publish_cpu_usage(client, get_total_cpu_usage())
                    except Exception as e:
                        if _is_reconnect_error(e):
                            raise
                        logger.exception("[CPU] publish failed")

                if MetricType.RAM in settings.metrics_to_log:
                    try:
                        await publish_ram_usage(client, get_memory_info())
                    except Exception as e:
                        if _is_reconnect_error(e):
                            raise
                        logger.exception("[RAM] publish failed")

                if MetricType.SERVICES in settings.metrics_to_log:
                    try:
                        if (
                            not settings.metrics_config.services
                            or not settings.metrics_config.services.names
                        ):
                            logger.warning(
                                "[SERVICES] No service names configured, skipping service info publishing"
                            )
                            continue
                        service_info = [
                            get_service_info(service_name)
                            for service_name in settings.metrics_config.services.names
                        ]
                        await publish_service_info(client, service_info)
                    except Exception as e:
                        if _is_reconnect_error(e):
                            raise
                        logger.exception("[SERVICES] publish failed")

                if MetricType.NETWORK in settings.metrics_to_log:
                    try:
                        await publish_network_usage(client, get_network_interfaces())
                    except Exception as e:
                        if _is_reconnect_error(e):
                            raise
                        logger.exception("[NETWORK] publish failed")

                if MetricType.KEPSERVER_EVENTS in settings.metrics_to_log:
                    try:
                        await publish_kep_event(client, get_kepserver_events())
                    except Exception as e:
                        if _is_reconnect_error(e):
                            raise
                        logger.exception("[EVENTS] publish failed")

                if MetricType.OPC_DIAGNOSTICS in settings.metrics_to_log and opc_reader:
                    try:
                        events = opc_reader.read_new_events()
                        await publish_opc_connection_events(client, events)
                    except Exception as e:
                        if _is_reconnect_error(e):
                            raise
                        logger.exception("[OPC_DIAGS] publish failed")

                try:
                    host_name = get_hostname()
                    await publish_host_name(client, host_name)
                except Exception as e:
                    if _is_reconnect_error(e):
                        raise
                    logger.exception("[HOSTNAME] publish failed")

                await asyncio.sleep(settings.polling_interval_seconds)
    except Exception as e:
        if not _is_reconnect_error(e):
            raise
        logger.warning(
            f"Connection lost ({type(e).__name__}: {e}), reconnecting in {_RECONNECT_DELAY}s..."
        )
        await asyncio.sleep(_RECONNECT_DELAY)
    finally:
        logger.info(f"Session uptime: {time.time() - start_time:.2f} seconds")


if __name__ == "__main__":
    # Match current implementation target (Windows-only service metrics).
    if os.name != "nt":
        raise RuntimeError("This extractor currently targets Windows.")
    asyncio.run(main())
