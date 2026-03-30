import argparse
import asyncio
import os

import time
from pathlib import Path
from metrics.events import get_kepserver_events
from metrics import (
    get_memory_info,
    get_network_interfaces,
    get_total_cpu_usage,
)
from lib.config import config, MetricType

def run_cycle(config) -> int:
    logged_system_count = 0

    if MetricType.CPU in config.logging_metrics:
        get_total_cpu_usage()
        logged_system_count += 1

    if MetricType.RAM in config.logging_metrics:
        total_kb, free_kb = get_memory_info()
        logged_system_count += 1

    if MetricType.SERVICES in config.logging_metrics:
        from metrics.services import get_service_info

        for service_name in config.service_names:
            get_service_info(service_name)
        logged_system_count += 1

    if MetricType.NETWORK in config.logging_metrics:
        for net in get_network_interfaces():
            pass
        logged_system_count += 1

    if MetricType.KEPSERVER_EVENTS in config.logging_metrics:
        for event in get_kepserver_events():
            pass
        logged_system_count += 1

    return logged_system_count


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collects computer and KepServer metrics."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run exactly one collection cycle and exit.",
    )
    parser.add_argument(
        "--settings",
        default=str(Path(__file__).resolve().parents[2] / "settings.json"),
        help="Path to settings.json",
    )
    args = parser.parse_args()
    config_path = Path(args.settings)

    try:
        while True:
            try:
                logged_count = run_cycle()
                print(f"Logged metrics for {logged_count} categories.")
            except Exception as exc:
                print(
                    f"Error occurred during metrics collection. Rolling back transaction. {exc}"
                )
                raise

            if args.once:
                break
            time.sleep(config.read_interval_ms / 1000.0)
    finally:
        database.close()


if __name__ == "__main__":
    # Match current implementation target (Windows-only service metrics).
    if os.name != "nt":
        raise RuntimeError("This extractor currently targets Windows.")
    asyncio.run(main())
