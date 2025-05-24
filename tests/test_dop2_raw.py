import pytest
from unittest.mock import AsyncMock

from asyncmiele import MieleClient


@pytest.fixture
def client():
    c = MieleClient(
        host="192.168.1.50",
        group_id=bytes.fromhex("0123456789abcdef"),
        group_key=bytes.fromhex("0123456789abcdef" * 8),
    )
    return c


@pytest.mark.asyncio
async def test_dop2_read_leaf_builds_correct_path(client):
    client._get_request = AsyncMock()
    client._get_request.return_value.data = b"\x00\x01"

    await client.read_dop2_leaf("0001", 2, 105, idx1=5, idx2=0)

    expected = "/Devices/0001/DOP2/2/105?idx1=5&idx2=0"
    client._get_request.assert_awaited_once_with(expected)


@pytest.mark.asyncio
async def test_dop2_write_leaf_builds_correct_path(client):
    client._put_request = AsyncMock(return_value=None)

    payload = b"\xDE\xAD\xBE\xEF"
    await client.write_dop2_leaf("0001", 2, 105, payload, idx1=1, idx2=2)

    expected = "/Devices/0001/DOP2/2/105?idx1=1&idx2=2"
    client._put_request.assert_awaited_once_with(expected, payload) 