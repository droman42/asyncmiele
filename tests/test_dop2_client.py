import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from asyncmiele import MieleClient
from asyncmiele.dop2.client import DOP2Client
from asyncmiele.dop2.models import DeviceCombinedState


@pytest.fixture
def miele_client():
    """Create a mock MieleClient for testing."""
    client = MagicMock(spec=MieleClient)
    client._get_raw = AsyncMock()
    client._put_request = AsyncMock()
    return client


@pytest.fixture
def dop2_client(miele_client):
    """Create a DOP2Client instance with a mock MieleClient."""
    return DOP2Client(miele_client)


@pytest.mark.asyncio
async def test_read_leaf_builds_correct_path(dop2_client, miele_client):
    """Test that read_leaf builds the correct path and calls _get_raw."""
    # Mock _get_raw to return a specific payload
    payload = b"\x00\x01\x02\x03"
    miele_client._get_raw.return_value = payload
    
    # Mock detector.register_leaf
    with patch('asyncmiele.dop2.client.detector.register_leaf') as mock_register:
        # Call read_leaf
        result = await dop2_client.read_leaf("device123", 2, 256, idx1=1, idx2=2)
        
        # Verify _get_raw was called with the correct path
        expected_path = "/Devices/device123/DOP2/2/256?idx1=1&idx2=2"
        miele_client._get_raw.assert_awaited_once_with(expected_path)
        
        # Verify detector.register_leaf was called
        mock_register.assert_called_once_with("device123", 2, 256)
        
        # Verify the result
        assert result == payload


@pytest.mark.asyncio
async def test_write_leaf_builds_correct_path(dop2_client, miele_client):
    """Test that write_leaf builds the correct path and calls _put_request."""
    # Mock _put_request
    miele_client._put_request.return_value = None
    
    # Mock detector.register_leaf
    with patch('asyncmiele.dop2.client.detector.register_leaf') as mock_register:
        # Call write_leaf
        payload = b"\x00\x01\x02\x03"
        await dop2_client.write_leaf("device123", 2, 256, payload, idx1=1, idx2=2)
        
        # Verify _put_request was called with the correct path and payload
        expected_path = "/Devices/device123/DOP2/2/256?idx1=1&idx2=2"
        miele_client._put_request.assert_awaited_once_with(expected_path, payload)
        
        # Verify detector.register_leaf was called
        mock_register.assert_called_once_with("device123", 2, 256)


@pytest.mark.asyncio
async def test_get_parsed_calls_read_leaf_and_parse_leaf(dop2_client):
    """Test that get_parsed calls read_leaf and parse_leaf with correct arguments."""
    # Mock read_leaf to return a specific payload
    payload = bytes([0, 0, 0, 1, 0, 2])  # 3x u16: 0, 1, 2
    dop2_client.read_leaf = AsyncMock(return_value=payload)
    
    # Mock parse_leaf to return a DeviceCombinedState
    expected_result = DeviceCombinedState(appliance_state=0, operation_state=1, process_state=2)
    with patch('asyncmiele.dop2.client.parse_leaf', return_value=expected_result) as mock_parse:
        result = await dop2_client.get_parsed("0001", 2, 256, idx1=0, idx2=0)
    
    # Verify read_leaf was called with correct arguments
    dop2_client.read_leaf.assert_awaited_once_with("0001", 2, 256, idx1=0, idx2=0)
    
    # Verify parse_leaf was called with correct arguments
    mock_parse.assert_called_once_with(2, 256, payload)
    
    # Verify the result
    assert result == expected_result


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


@pytest.mark.asyncio
async def test_integration_with_miele_client():
    """Test integration between MieleClient and DOP2Client."""
    # Create a MieleClient with mocked methods
    client = MagicMock(spec=MieleClient)
    client._get_raw = AsyncMock(return_value=b"\x00\x01\x00\x02")
    
    # Create a DOP2Client instance
    dop2_client = DOP2Client(client)
    
    # Mock the get_dop2_client method to return our DOP2Client
    client.get_dop2_client = MagicMock(return_value=dop2_client)
    
    # Call the method
    result = client.get_dop2_client()
    
    # Verify the result
    assert result == dop2_client
    assert result.client == client 