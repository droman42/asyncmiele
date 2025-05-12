import pytest
from unittest.mock import AsyncMock

from asyncmiele import MieleClient
from asyncmiele.config import settings


@pytest.fixture
def client():
    return MieleClient(
        host="192.168.1.50",
        group_id=bytes.fromhex("0123456789abcdef"),
        group_key=bytes.fromhex("0123456789abcdef" * 8),
    )


@pytest.mark.asyncio
async def test_remote_start_disabled(client):
    """Calling remote_start without enabling should raise."""
    with pytest.raises(PermissionError):
        await client.remote_start("0001")


@pytest.mark.asyncio
async def test_remote_start_enabled(client):
    settings.enable_remote_start = True
    client._put_request = AsyncMock(return_value=None)

    await client.remote_start("0001")

    client._put_request.assert_awaited_once()
    called_res, called_body = client._put_request.call_args[0]
    assert called_res == "/Devices/0001/State"
    assert called_body == {"ProcessAction": 1}

    settings.enable_remote_start = False  # reset for other tests 