import pytest
from unittest.mock import patch

from asyncmiele import MieleClient


class MockResponse:
    def __init__(self, status=204, body=b"", headers=None):
        self.status = status
        self._body = body
        self.headers = headers or {}

    async def read(self):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def client():
    return MieleClient(
        host="192.168.1.50",
        group_id=bytes.fromhex("0123456789abcdef"),
        group_key=bytes.fromhex("0123456789abcdef" * 8),
    )


@pytest.mark.asyncio
@patch("aiohttp.ClientSession.put")
async def test_put_request_204(mock_put, client):
    """PUT helper should return None on 204 response."""
    mock_put.return_value = MockResponse(status=204)

    result = await client._put_request("/Devices/0001/State", {"DeviceAction": 2})
    assert result is None
    mock_put.assert_called_once() 