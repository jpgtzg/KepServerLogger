"""
Ingestor for retrieving data from the OPC UA server and ingesting it into the database.

Reads the tags from a .csv file and ingests the data into the database.
"""

from lib.constants import format_timestamp
from lib.tag_extractor import extract_tags
from lib.opcua_client import OPCUAClient
from lib.config import Config
from db import TagsDatabase
import asyncio


async def main():
    config = Config.load()

    print(f"Connecting to {config.kepserver_server_url}...")

    tags = extract_tags(
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

    db = TagsDatabase(retention_days=config.log_retention_days)
    db.initialize()

    async with client:
        try:
            while True:
                tag_values, timestamp = await client.read_batch(tags)

                print(
                    f"Logged {len(tag_values)} values for {len(tags)} tags at {format_timestamp(timestamp, config.timestamp_format)}"
                )
                db.save_many(tag_values, timestamp)

                await asyncio.sleep(1)

        except KeyboardInterrupt:
            print("Stopping logger...")

        finally:
            print("Disconnected.")


if __name__ == "__main__":
    asyncio.run(main())
