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
async def test_put_request_204(client):
    """PUT helper should return None on 204 response."""
    # Mock the underlying _request_bytes method to return 204 status
    with patch.object(client, '_request_bytes') as mock_request:
        mock_request.return_value = (204, b"")
        
        result = await client._put_request("/Devices/0001/State", {"DeviceAction": 2})
        
        # Verify the result
        assert result is None
        
        # Verify the request was made with correct parameters
        mock_request.assert_called_once_with(
            "PUT",
            "/Devices/0001/State",
            body={"DeviceAction": 2},
            allowed_status=(200, 204)
        ) 