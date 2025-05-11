"""
Tests for the MieleClient class.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

from asyncmiele import MieleClient
from asyncmiele.models.response import MieleResponse
from asyncmiele.models.device import MieleDevice


class MockResponse:
    """Mock for aiohttp response."""
    
    def __init__(self, data, status=200):
        self.data = data
        self.status = status
        self.headers = {
            'X-Signature': 'signature:123456789abcdef'
        }
        
    async def read(self):
        """Read response body."""
        return self.data
        
    async def __aenter__(self):
        """Context manager enter."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        pass


@pytest.fixture
def mock_client():
    """Create a mocked MieleClient instance."""
    client = MieleClient(
        host="192.168.1.123",
        group_id=bytes.fromhex("0123456789abcdef"),
        group_key=bytes.fromhex("0123456789abcdef" * 8)
    )
    return client


@pytest.mark.asyncio
@patch('aiohttp.ClientSession.get')
@patch('asyncmiele.utils.crypto.decrypt_response')
async def test_get_devices(mock_decrypt, mock_get, mock_client):
    """Test getting devices from the API."""
    # Sample decrypted response
    decrypted_data = json.dumps({
        "1234": {
            "Ident": {
                "DeviceName": "Dishwasher",
                "DeviceIdentLabel": {
                    "FabNumber": "000000000000",
                    "TechType": "Dishwasher",
                },
                "Type": {
                    "value_raw": 7,
                    "value_localized": "Dishwasher"
                }
            },
            "State": {
                "status": {
                    "value_raw": 1,
                    "value_localized": "Running"
                },
                "programPhase": {
                    "value_raw": 5,
                    "value_localized": "Washing"
                }
            }
        }
    }).encode()
    
    # Mock the response and decryption
    mock_get.return_value = MockResponse(b"encrypted_data")
    mock_decrypt.return_value = decrypted_data
    
    # Get devices
    devices = await mock_client.get_devices()
    
    # Verify results
    assert len(devices) == 1
    assert "1234" in devices
    
    device = devices["1234"]
    assert device.id == "1234"
    assert device.name == "Dishwasher"
    assert device.ident.fab_number == "000000000000"
    assert device.ident.tech_type == "Dishwasher"
    assert device.state.status == "Running"
    assert device.state.program_phase == "Washing"


@pytest.mark.asyncio
@patch('aiohttp.ClientSession.put')
async def test_register(mock_put, mock_client):
    """Test device registration."""
    # Mock successful registration
    mock_put.return_value = MockResponse(b"", 200)
    
    # Register with the device
    result = await mock_client.register()
    
    # Verify results
    assert result is True
    mock_put.assert_called_once() 