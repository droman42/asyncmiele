import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from asyncmiele import MieleClient
from asyncmiele.dop2.client import DOP2Client
from asyncmiele.dop2.models import DeviceCombinedState


@pytest.fixture
def miele_client():
    """Create a mock MieleClient for testing."""
    client = MagicMock(spec=MieleClient)
    client.read_dop2_leaf = AsyncMock()
    client.write_dop2_leaf = AsyncMock()
    client.get_parsed_dop2_leaf = AsyncMock()
    return client


@pytest.fixture
def dop2_client():
    """Create a DOP2Client instance as a pure protocol handler."""
    return DOP2Client()


def test_leaf_constants(dop2_client):
    """Test that DOP2Client has the correct leaf constants."""
    assert dop2_client.LEAF_HOURS_OF_OPERATION == (2, 119)
    assert dop2_client.LEAF_CYCLE_COUNTER == (2, 138)
    assert dop2_client.LEAF_COMBINED_STATE == (2, 256)
    assert dop2_client.LEAF_PROGRAM_LIST == (2, 1584)


def test_build_leaf_path(dop2_client):
    """Test that build_leaf_path builds the correct path."""
    path = dop2_client.build_leaf_path("device123", 2, 256, idx1=1, idx2=2)
    expected_path = "/Devices/device123/DOP2/2/256?idx1=1&idx2=2"
    assert path == expected_path


def test_build_sf_value_payload(dop2_client):
    """Test that build_sf_value_payload builds the correct payload."""
    with patch('asyncmiele.dop2.client.write_u16') as mock_write_u16:
        # Configure mock to return specific values for each call
        mock_write_u16.side_effect = [b"\x00\x01", b"\x00\x02"]
        
        # Call the method
        result = dop2_client.build_sf_value_payload(1, 2)
        
        # Verify write_u16 was called correctly
        assert mock_write_u16.call_count == 2
        mock_write_u16.assert_any_call(1)
        mock_write_u16.assert_any_call(2)
        
        # Verify the result is the concatenation of the two write_u16 calls
        assert result == b"\x00\x01\x00\x02"


def test_build_program_selection_payload(dop2_client):
    """Test that build_program_selection_payload calls the correct function."""
    mock_payload = b"\x00\x01\x02\x03"
    
    with patch('asyncmiele.dop2.client.build_program_selection', return_value=mock_payload) as mock_build:
        payload = dop2_client.build_program_selection_payload(1, {2: 3})
    
    mock_build.assert_called_once_with(1, {2: 3})
    assert payload == mock_payload


def test_parse_leaf_response(dop2_client):
    """Test that parse_leaf_response calls parse_leaf."""
    with patch('asyncmiele.dop2.client.parse_leaf') as mock_parse_leaf:
        mock_parse_leaf.return_value = "parsed_result"
        
        result = dop2_client.parse_leaf_response(2, 256, b"\x00\x01\x02")
        
        mock_parse_leaf.assert_called_once_with(2, 256, b"\x00\x01\x02")
        assert result == "parsed_result"


@pytest.mark.asyncio
async def test_integration_with_miele_client():
    """Test integration between MieleClient and DOP2Client."""
    # Create a MieleClient with mocked DOP2 methods
    client = MagicMock(spec=MieleClient)
    client.read_dop2_leaf = AsyncMock(return_value=b"\x00\x01\x00\x02")
    client.get_dop2_client = MagicMock()
    
    # Test that MieleClient has the expected DOP2 methods
    assert hasattr(client, 'read_dop2_leaf')
    assert hasattr(client, 'write_dop2_leaf') 
    assert hasattr(client, 'get_parsed_dop2_leaf')
    
    # Test that DOP2Client can be created independently
    dop2_client = DOP2Client()
    assert dop2_client is not None
    assert hasattr(dop2_client, 'build_leaf_path')
    assert hasattr(dop2_client, 'parse_leaf_response') 