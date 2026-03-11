from asyncua import Client, ua
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
from src.logger import save_many_to_db, periodic_cleanup
from src.tag_extractor import extract_tags, PREFIX
from dotenv import load_dotenv
import os
import asyncio
from datetime import datetime

load_dotenv()

CLIENT_USERNAME = os.getenv("CLIENT_USERNAME")
CLIENT_PASSWORD = os.getenv("CLIENT_PASSWORD")
APP_URI = os.getenv("APP_URI")
SERVER_URL = os.getenv("SERVER_URL")
APPLICATION_NAME = os.getenv("APPLICATION_NAME")

CERT_PATH = "certs/client_cert.pem"
KEY_PATH  = "certs/client_key.pem"

TAGS = extract_tags(save_to_file=False)

async def main():
    print(f"Connecting to {SERVER_URL}...")

    client = Client(url=SERVER_URL)
    client.application_uri = APP_URI
    client.name = APPLICATION_NAME

    await client.set_security(
        SecurityPolicyBasic256Sha256,
        CERT_PATH,
        KEY_PATH,
        mode=ua.MessageSecurityMode.SignAndEncrypt,
    )

    client.set_user(CLIENT_USERNAME)
    client.set_password(CLIENT_PASSWORD)

    async with client:
        print("Connected to KepServer")
        server_time = client.get_node("ns=0;i=2258")
        print(await server_time.read_value())

        asyncio.create_task(periodic_cleanup())

        try:
            while True:
                nodes = [client.get_node(tag) for tag in TAGS]
                values = await client.read_attributes(nodes, ua.AttributeIds.Value)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                tag_values = [
                    (node.nodeid.to_string().removeprefix(PREFIX), value)
                    for node, value in zip(nodes, values)
                ]

                print( f"Logged {len(tag_values)} values for {len(nodes)} nodes at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                save_many_to_db(tag_values, timestamp)

                await asyncio.sleep(1)

        except KeyboardInterrupt:
            print("Stopping logger...")

        finally:
            print("Disconnected.") 

if __name__ == "__main__":
    asyncio.run(main())
