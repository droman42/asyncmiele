import pytest
from unittest.mock import AsyncMock

from asyncmiele import MieleClient


@pytest.fixture
def client():
    return MieleClient(
        host="192.168.1.50",
        group_id=bytes.fromhex("0123456789abcdef"),
        group_key=bytes.fromhex("0123456789abcdef" * 8),
    )


@pytest.mark.asyncio
async def test_wake_up(client):
    client._put_request = AsyncMock(return_value=None)

    await client.wake_up("0001")

    client._put_request.assert_awaited_once()
    called_resource, called_body = client._put_request.call_args[0]
    assert called_resource == "/Devices/0001/State"
    assert called_body == {"DeviceAction": 2} 