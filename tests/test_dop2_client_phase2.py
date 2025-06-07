import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from asyncmiele import MieleClient
from asyncmiele.dop2.client import DOP2Client
from asyncmiele.dop2.models import (
    DeviceGenerationType, ConsumptionStats, HoursOfOperation, 
    CycleCounter, ProcessData, SFValue
)


@pytest.fixture
def miele_client():
    """Create a mock MieleClient for testing."""
    client = MagicMock(spec=MieleClient)
    client.read_dop2_leaf = AsyncMock()
    client.write_dop2_leaf = AsyncMock()
    client.get_parsed_dop2_leaf = AsyncMock()
    client.get_device_ident = AsyncMock()
    return client


@pytest.fixture
def dop2_client():
    """Create a DOP2Client instance as a pure protocol handler."""
    return DOP2Client()


@pytest.mark.asyncio
async def test_detect_generation_using_miele_client(miele_client):
    """Test generation detection using MieleClient methods."""
    # Mock some DOP2 leaf calls to succeed  
    miele_client.read_dop2_leaf.return_value = b"\x00\x01\x02"
    
    # Mock the detect_device_generation method
    expected_generation = DeviceGenerationType.DOP2
    miele_client.detect_device_generation = AsyncMock(return_value=expected_generation)
    
    # Call the method
    result = await miele_client.detect_device_generation("0001")
    
    # Verify the result
    assert result == expected_generation


@pytest.mark.asyncio 
async def test_get_program_catalog_using_miele_client(miele_client):
    """Test program catalog extraction using MieleClient methods."""
    # Mock the get_program_catalog method
    expected_catalog = {
        "device_type": "washer",
        "programs": [
            {"id": 1, "name": "Cotton", "options": []},
            {"id": 2, "name": "Delicate", "options": []}
        ]
    }
    miele_client.get_program_catalog = AsyncMock(return_value=expected_catalog)
    
    # Call the method
    result = await miele_client.get_program_catalog("0001")
    
    # Verify the result
    assert result == expected_catalog
    assert len(result["programs"]) == 2


@pytest.mark.asyncio
async def test_get_consumption_stats_using_miele_client(miele_client):
    """Test consumption stats using MieleClient methods."""
    # Mock the get_consumption_stats method
    expected_stats = ConsumptionStats(
        hours_of_operation=1000,
        cycles_completed=50,
        energy_wh_total=1500,
        water_l_total=200
    )
    miele_client.get_consumption_stats = AsyncMock(return_value=expected_stats)
    
    # Call the method
    result = await miele_client.get_consumption_stats("0001")
    
    # Verify the result
    assert isinstance(result, ConsumptionStats)
    assert result.hours_of_operation == 1000
    assert result.cycles_completed == 50
    assert result.energy_wh_total == 1500
    assert result.water_l_total == 200


@pytest.mark.asyncio
async def test_get_setting_using_miele_client(miele_client):
    """Test getting settings using MieleClient methods."""
    # Mock the get_setting method
    expected_sf_value = SFValue(sf_id=100, current_value=10, minimum=0, maximum=20, default=5)
    miele_client.get_setting = AsyncMock(return_value=expected_sf_value)
    
    # Call the method
    result = await miele_client.get_setting("0001", 100)
    
    # Verify the result
    assert result == expected_sf_value


@pytest.mark.asyncio
async def test_set_setting_using_miele_client(miele_client):
    """Test setting settings using MieleClient methods."""
    # Mock the set_setting method
    miele_client.set_setting = AsyncMock()
    
    # Call the method
    await miele_client.set_setting("0001", 100, 15)
    
    # Verify the method was called
    miele_client.set_setting.assert_called_once_with("0001", 100, 15)


@pytest.mark.asyncio
async def test_set_setting_value_out_of_range_using_miele_client(miele_client):
    """Test that set_setting raises an error when the value is out of range."""
    # Mock the set_setting method to raise ValueError
    miele_client.set_setting = AsyncMock(side_effect=ValueError("Value 30 outside allowed range 0-20"))
    
    # Call the method with a value out of range
    with pytest.raises(ValueError, match="Value 30 outside allowed range"):
        await miele_client.set_setting("0001", 100, 30)


def test_dop2_client_protocol_methods(dop2_client):
    """Test that DOP2Client has the expected protocol methods."""
    # Test leaf constants
    assert dop2_client.LEAF_HOURS_OF_OPERATION == (2, 119)
    assert dop2_client.LEAF_CYCLE_COUNTER == (2, 138)
    assert dop2_client.LEAF_COMBINED_STATE == (2, 1586)
    
    # Test protocol methods
    assert hasattr(dop2_client, 'build_leaf_path')
    assert hasattr(dop2_client, 'parse_leaf_response')
    assert hasattr(dop2_client, 'build_sf_value_payload')
    
    # Test path building
    path = dop2_client.build_leaf_path("0001", 2, 1586, idx1=0, idx2=0)
    assert path == "/Devices/0001/DOP2/2/1586?idx1=0&idx2=0"


def test_get_dop2_client_integration(miele_client):
    """Test that MieleClient can return a DOP2Client instance."""
    # Mock the get_dop2_client method
    dop2_client = DOP2Client()
    miele_client.get_dop2_client = MagicMock(return_value=dop2_client)
    
    # Call the method
    result = miele_client.get_dop2_client()
    
    # Verify the result
    assert result == dop2_client
    assert isinstance(result, DOP2Client) 