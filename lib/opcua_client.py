"""
Generic OPC UA client class, inherits from asyncua.Client and adds security and authentication.
"""

from datetime import datetime
from logging import getLogger

from asyncua import Client, ua
from asyncua.common.node import Node
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256

from lib.utils import utcnow

logger = getLogger(__name__)


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
        self.application_uri: str = app_uri
        self.name: str = name
        self._cert_path: str = cert_path
        self._key_path: str = key_path
        self._username: str | None = username
        self._password: str | None = password

        self._ready: bool = False

    async def setup(self) -> None:
        """Call this after __init__ before connecting."""
        logger.info("Setting up OPC UA client...")
        await self.set_security(
            SecurityPolicyBasic256Sha256,
            self._cert_path,
            self._key_path,
            mode=ua.MessageSecurityMode.SignAndEncrypt,
        )
        if self._username and self._password:
            self.set_user(self._username)
            self.set_password(self._password)
        else:
            raise ValueError(
                "Username and password are required for OPC UA client authentication"
            )

        self._ready = True
        logger.info("OPC UA client setup complete")

    async def read_batch(
        self,
        tags: list[str],
        prefix: str,
    ) -> tuple[list[tuple[str, ua.DataValue]], datetime]:
        if not self._ready:
            raise RuntimeError("Client not ready, call setup() first")

        nodes = [self.get_node(tag) for tag in tags]
        values = await self.read_attributes(nodes, ua.AttributeIds.Value)
        timestamp = utcnow()

        tag_values = [
            (
                node.nodeid.to_string().removeprefix(prefix + "."),
                value,
            )
            for node, value in zip(nodes, values)
        ]

        return tag_values, timestamp

    async def write_value(
        self, node: Node, value: float | int | str | bool, data_type: ua.VariantType
    ) -> None:
        if not self._ready:
            raise RuntimeError("Client not ready, call setup() first")

        # KepServer nodes are often configured as Strings, even for numeric values.
        # If we try to send a float/int to a String-typed node, asyncua will attempt
        # to encode it as bytes and fail (e.g. "'float' object has no attribute 'encode'").
        coerced_value: float | int | str | bool = value
        if data_type == ua.VariantType.String and not isinstance(value, str):
            coerced_value = str(value)
        elif data_type in (ua.VariantType.Float, ua.VariantType.Double) and isinstance(
            value, str
        ):
            coerced_value = float(value)
        elif data_type in (
            ua.VariantType.Int16,
            ua.VariantType.Int32,
            ua.VariantType.Int64,
            ua.VariantType.UInt16,
            ua.VariantType.UInt32,
            ua.VariantType.UInt64,
        ) and isinstance(value, str):
            coerced_value = int(value)
        elif data_type == ua.VariantType.Boolean and isinstance(value, str):
            coerced_value = value.strip().lower() in ("1", "true", "yes", "y", "on")

        await node.write_attribute(
            ua.AttributeIds.Value,
            ua.DataValue(ua.Variant(coerced_value, data_type)),
        )
