import pytest
from unittest.mock import AsyncMock, patch

from asyncmiele import MieleClient
from asyncmiele.dop2.models import SFValue


@pytest.fixture
def client():
    return MieleClient(
        host="192.168.1.50",
        group_id=bytes.fromhex("0123456789abcdef"),
        group_key=bytes.fromhex("0123456789abcdef" * 8),
    )


@pytest.mark.asyncio
async def test_get_setting(client):
    sf = SFValue(sf_id=100, current_value=10, minimum=0, maximum=20, default=5)
    
    # Mock the get_parsed_dop2_leaf method that actually exists
    with patch.object(client, 'get_parsed_dop2_leaf', return_value=sf) as mock_get_parsed:
        result = await client.get_setting("0001", 100)
        
        assert result is sf
        # Verify the correct leaf was accessed for SF_VALUE
        mock_get_parsed.assert_called_once()


@pytest.mark.asyncio
async def test_set_setting_validation(client):
    sf = SFValue(sf_id=100, current_value=10, minimum=0, maximum=20, default=5)
    
    # Mock both the get and write methods
    with patch.object(client, 'get_parsed_dop2_leaf', return_value=sf) as mock_get_parsed, \
         patch.object(client, 'write_dop2_leaf') as mock_write_leaf:
        
        # Test invalid value (outside range)
        with pytest.raises(ValueError):
            await client.set_setting("0001", 100, 30)
        
        # Test valid value (within range)
        await client.set_setting("0001", 100, 15)
        
        # Verify the write was called for the valid case
        mock_write_leaf.assert_called_once() 