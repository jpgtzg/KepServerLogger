"""
Standard handlers for different formats to an OPC UA server

"""

import json
from collections.abc import Callable, Sequence
from logging import getLogger
from typing import TypeVar

from asyncua import ua

from lib.models import OPCUAModel
from lib.monitor import OPCUAMonitor
from lib.opcua_client import OPCUAClient

logger = getLogger(__name__)

T = TypeVar("T", bound=OPCUAModel)


async def safe_handle(
    metric: str,
    monitor: OPCUAMonitor,
    coro,
    on_error_hook: Callable[[Exception], object] | None = None,
) -> None:
    try:
        await coro
        monitor.on_success(metric)
    except ConnectionError:
        raise
    except Exception as e:
        logger.exception(f"[{metric}] publish failed")
        if on_error_hook is not None:
            on_error_hook(e)
        monitor.on_failure(metric)


async def publish_scalar(
    client: OPCUAClient, data: OPCUAModel, prefix: str, logging_str: str
) -> None:
    """
    Publish a scalarar values from an OPCUAModel to the OPC UA server.

    Args:
        client (OPCUAClient): The OPC UA client instance.
        data (OPCUAModel): The data to publish.
    """

    logger.info(logging_str)
    for field, value in data.to_opcua().items():
        node = client.get_node(f"{prefix}.{field}")
        variant_type = await node.read_data_type_as_variant_type()
        await client.write_value(node, value, variant_type)


async def publish_batch(
    client: OPCUAClient, data: Sequence[OPCUAModel], prefix: str, logging_str: str
) -> None:
    """
    Publishes a batch of values as a json-encoded string in a tag in an OPC UA server.

    Args:
        client (OPCUAClient): The OPC UA client instance.
        data (list[OPCUAModel]): The data to publish.
    """
    logger.info(logging_str)
    payload = [item.to_opcua() for item in data]
    node = client.get_node(f"{prefix}.batch")
    await client.write_value(node, json.dumps(payload), ua.VariantType.String)


async def subscribe_scalar(client: OPCUAClient, prefix: str, model_class: type[T]) -> T:
    """
    Subscribe to a scalar value from an OPC UA server.

    Args:
        client (OPCUAClient): The OPC UA client instance.
        prefix (str): The prefix of the tag to subscribe to.
        model_class (Type[OPCUAModel]): The model class to use for the data.
    Returns:
        T: An instance of the model class initialized with the retrieved data.
    """
    data = {}
    for field in model_class.model_fields:
        node = client.get_node(f"{prefix}.{field}")
        data[field] = await node.read_value()
    return model_class(**data)


async def subscribe_batch(
    client: OPCUAClient, prefix: str, model_class: type[T]
) -> list[T]:
    """
    Subscribe to a batch of values from an OPC UA server.

    Args:
        client (OPCUAClient): The OPC UA client instance.
        prefix (str): The prefix of the tag to subscribe to.
        model_class (Type[OPCUAModel]): The model class to use for the data.
    Returns:
        list[T]: A list of instances of the model class initialized with the retrieved data.
    """
    node = client.get_node(f"{prefix}.batch")
    raw: str = await node.read_value()
    if not raw:
        return []
    payload = json.loads(raw)
    return [model_class(**item) for item in payload]
