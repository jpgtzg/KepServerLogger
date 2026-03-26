"""
Generic OPC UA client class, inherits from asyncua.Client and adds security and authentication.
"""

from asyncua import Client, ua
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
from datetime import datetime, timezone
from lib.constats import PREFIX
from typing import Any


class OPCUAClient(Client):
    async def __init__(
        self,
        url: str,
        app_uri: str,
        name: str,
        cert_path: str,
        key_path: str,
        username: str,
        password: str,
    ):
        super().__init__(url)
        self.application_uri = app_uri
        self.name = name

        await self.set_security(
            SecurityPolicyBasic256Sha256,
            cert_path,
            key_path,
            mode=ua.MessageSecurityMode.SignAndEncrypt,
        )

        self.set_user(username)
        self.set_password(password)

    async def read_batch(
        self, tags: list[str]
    ) -> tuple[list[tuple[str, Any]], datetime]:
        nodes = [self.get_node(tag) for tag in tags]
        values = await self.read_attributes(nodes, ua.AttributeIds.Value)
        timestamp = datetime.now(timezone.utc)

        tag_values = [
            (node.nodeid.to_string().removeprefix(PREFIX), value)
            for node, value in zip(nodes, values)
        ]

        return tag_values, timestamp
