from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from config import MetricType, load_config
from db import Database
from events import get_events
from metrics import (
    get_memory_info,
    get_network_interfaces,
    get_total_cpu_usage,
)


def load_environment() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv(repo_root / ".env", override=True)
    # Allow running from repo root or extractor folder.
    if Path(".env").exists():
        load_dotenv(".env", override=True)


def run_cycle(database: Database, config) -> int:
    logged_system_count = 0

    with database.transaction():
        if MetricType.CPU in config.logging_metrics:
            database.insert_cpu_usage(get_total_cpu_usage())
            logged_system_count += 1

        if MetricType.RAM in config.logging_metrics:
            total_kb, free_kb = get_memory_info()
            database.insert_ram_usage(total_kb, free_kb)
            logged_system_count += 1

        if MetricType.SERVICES in config.logging_metrics:
            from metrics.services import get_service_info

            for service_name in config.service_names:
                database.insert_service_info(get_service_info(service_name))
            logged_system_count += 1

        if MetricType.NETWORK in config.logging_metrics:
            for net in get_network_interfaces():
                database.insert_network_metrics(
                    interface=str(net["interface"]),
                    operational_status=str(net["operational_status"]),
                    network_interface_type=str(net["network_interface_type"]),
                    kb_bytes_sent=float(net["kb_bytes_sent"]),
                    kb_bytes_received=float(net["kb_bytes_received"]),
                )
            logged_system_count += 1

        if MetricType.KEPSERVER_EVENTS in config.logging_metrics:
            for event in get_events():
                database.insert_event(event)
            logged_system_count += 1

    return logged_system_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Collects computer and KepServer metrics.")
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

    load_environment()
    config = load_config(config_path)

    database = Database()
    database.initialize()
    print("Database initialized successfully.")

    try:
        while True:
            try:
                logged_count = run_cycle(database, config)
                print(f"Logged metrics for {logged_count} categories.")
            except Exception as exc:
                print(f"Error occurred during metrics collection. Rolling back transaction. {exc}")
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
    main()