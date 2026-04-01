"""
Generic OPC UA client class, inherits from asyncua.Client and adds security and authentication.
"""

from asyncua import Client, ua
from asyncua.common.node import Node
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
from lib.tag_extractor import TAG_PREFIX
from datetime import datetime
from lib.utils import utcnow
from typing import Any


class OPCUAClient(Client):
    def __init__(
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
        self._cert_path = cert_path
        self._key_path = key_path
        self._username = username
        self._password = password

        self._ready = False

    async def setup(self) -> None:
        """Call this after __init__ before connecting."""
        await self.set_security(
            SecurityPolicyBasic256Sha256,
            self._cert_path,
            self._key_path,
            mode=ua.MessageSecurityMode.SignAndEncrypt,
        )
        self.set_user(self._username)
        self.set_password(self._password)

        self._ready = True

    async def read_batch(
        self, tags: list[str]
    ) -> tuple[list[tuple[str, Any]], datetime]:
        if not self._ready:
            raise RuntimeError("Client not ready, call setup() first")

        nodes = [self.get_node(tag) for tag in tags]
        values = await self.read_attributes(nodes, ua.AttributeIds.Value)
        timestamp = utcnow()

        tag_values = [
            (node.nodeid.to_string().removeprefix(TAG_PREFIX), value)
            for node, value in zip(nodes, values)
        ]

        return tag_values, timestamp

    async def write_value(
        self, node: Node, value: float | int | str | bool, data_type: ua.VariantType
    ) -> None:
        if not self._ready:
            raise RuntimeError("Client not ready, call setup() first")

        await node.write_attribute(
            ua.AttributeIds.Value, ua.DataValue(ua.Variant(value, data_type))
        )
