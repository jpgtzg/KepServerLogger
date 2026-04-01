"""
Ingestor for retrieving data from the OPC UA server and ingesting it into the database.

Reads the tags from a .csv file and ingests the data into the database.

## This ingestor will log the following metrics:
- Tags

- CPU Usage
- RAM Usage
- Network Usage
- Services Usage
- KepServer Events
"""

import asyncio

from db import TagsDatabase

from lib.config import config, MetricType
from lib.opcua_client import OPCUAClient
from lib.tag_extractor import extract_tags


async def main():
    print(f"Connecting to {config.kepserver_server_url}...")

    tags_to_log = extract_tags(
        use_prefix=True,
        separator=config.csv_tag_separator,
        exclude_tags=config.csv_exclude_tags,
        tag_column=config.csv_tag_column_name,
        filename=config.csv_filename,
    )

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

    db = TagsDatabase(retention_days=config.log_retention_days)
    db.initialize()

    async with client:
        try:
            while True:
                if MetricType.TAGS in config.logging_metrics:
                    tag_values, timestamp = await client.read_batch(tags_to_log)

                    print(
                        f"Logged {len(tag_values)} values for {len(tags_to_log)} tags at {timestamp.strftime(config.timestamp_format)}"
                    )
                    rows = db.process_tag_values(tag_values, timestamp)
                    db.save_many(rows)
                    print(f"Saved {len(rows)} tags to the database")

                if MetricType.CPU in config.logging_metrics:
                    # TODO: IMPLEMENT
                    pass
                if MetricType.RAM in config.logging_metrics:
                    # TODO: IMPLEMENT
                    pass
                if MetricType.NETWORK in config.logging_metrics:
                    # TODO: IMPLEMENT
                    pass
                if MetricType.SERVICES in config.logging_metrics:
                    # TODO: IMPLEMENT
                    pass
                if MetricType.KEPSERVER_EVENTS in config.logging_metrics:
                    # TODO: IMPLEMENT
                    pass

                await asyncio.sleep(1)

        except KeyboardInterrupt:
            print("Stopping logger...")

        finally:
            print("Disconnected.")


if __name__ == "__main__":
    asyncio.run(main())
