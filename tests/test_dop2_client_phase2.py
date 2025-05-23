import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from asyncmiele import MieleClient
from asyncmiele.dop2.client import DOP2Client
from asyncmiele.dop2.models import (
    DeviceCombinedState, SFValue, DeviceGenerationType,
    HoursOfOperation, CycleCounter, ProcessData, ConsumptionStats
)


@pytest.fixture
def miele_client():
    """Create a mock MieleClient for testing."""
    client = MagicMock(spec=MieleClient)
    client._get_raw = AsyncMock()
    client._put_request = AsyncMock()
    client.get_device_ident = AsyncMock()
    return client


@pytest.fixture
def dop2_client(miele_client):
    """Create a DOP2Client instance with a mock MieleClient."""
    return DOP2Client(miele_client)


@pytest.mark.asyncio
async def test_detect_generation(dop2_client):
    """Test that detect_generation calls the correct methods and returns the correct result."""
    # Mock the detector.get_available_leaves method
    with patch('asyncmiele.dop2.client.detector.get_available_leaves', return_value=[]) as mock_get_leaves:
        # Mock the read_leaf method
        dop2_client.read_leaf = AsyncMock()
        
        # Mock the detector.detect_generation method
        expected_generation = DeviceGenerationType.DOP2
        with patch('asyncmiele.dop2.client.detector.detect_generation', return_value=expected_generation) as mock_detect:
            # Call the method
            result = await dop2_client.detect_generation("0001")
            
            # Verify the correct methods were called
            mock_get_leaves.assert_called_once_with("0001")
            assert dop2_client.read_leaf.call_count == 3
            mock_detect.assert_called_once_with("0001")
            
            # Verify the result
            assert result == expected_generation


@pytest.mark.asyncio
async def test_get_program_catalog_primary(dop2_client, miele_client):
    """Test that _get_program_catalog_primary calls the correct methods and returns the correct result."""
    # Mock the get_parsed method to return program list data
    program_list_data = {"programIds": [1, 2, 3]}
    dop2_client.get_parsed = AsyncMock(side_effect=[
        program_list_data,  # For program list
        {"options": [{"id": 1, "value": 10}]},  # For options of program 1
        {"options": [{"id": 2, "value": 20}]},  # For options of program 2
        {"options": [{"id": 3, "value": 30}]}   # For options of program 3
    ])
    
    # Mock the get_device_ident method
    from asyncmiele.models.device import DeviceIdentification
    ident = DeviceIdentification(device_type="1", tech_type="Washer")
    miele_client.get_device_ident.return_value = ident
    
    # Mock DeviceType enum
    with patch('asyncmiele.dop2.client.DeviceType') as mock_device_type:
        mock_device_type.return_value.name = "WASHING_MACHINE"
        
        # Call the method
        result = await dop2_client._get_program_catalog_primary("0001")
        
        # Verify the correct methods were called
        dop2_client.get_parsed.assert_any_call("0001", *dop2_client.LEAF_PROGRAM_LIST)
        miele_client.get_device_ident.assert_called_once_with("0001")
        
        # Verify the result
        assert result["device_type"] == "1"
        assert len(result["programs"]) == 3
        assert result["programs"][0]["id"] == 1
        assert result["programs"][1]["id"] == 2
        assert result["programs"][2]["id"] == 3
        assert result["programs"][0]["options"] == [{"id": 1, "value": 10}]


@pytest.mark.asyncio
async def test_get_program_catalog_legacy(dop2_client, miele_client):
    """Test that _get_program_catalog_legacy calls the correct methods and returns the correct result."""
    # Mock the read_leaf method
    program_list_data = b"\x00\x01\x00\x10\x00\x01"  # Program ID 1, name ID 16, option group 1
    option_list_data = b"\x00\x02\x00\x20\x00\x05"   # Option ID 2, name ID 32, default 5
    string_table_data = b"Program 1\x00Option 2\x00"
    
    dop2_client.read_leaf = AsyncMock(side_effect=[
        program_list_data,  # For program list
        option_list_data,   # For options
        string_table_data   # For string table
    ])
    
    # Mock the parse functions
    with patch('asyncmiele.dop2.client.parse_program_list', return_value=[{"id": 1, "name_id": 16, "option_group": 1}]) as mock_parse_programs:
        with patch('asyncmiele.dop2.client.parse_option_list', return_value=[{"id": 2, "name_id": 32, "default": 5}]) as mock_parse_options:
            with patch('asyncmiele.dop2.client.build_string_map', return_value={0: "Program 1", 1: "Option 2"}) as mock_build_strings:
                # Mock the get_device_ident method
                from asyncmiele.models.device import DeviceIdentification
                ident = DeviceIdentification(device_type="1", tech_type="Washer")
                miele_client.get_device_ident.return_value = ident
                
                # Mock DeviceType enum
                with patch('asyncmiele.dop2.client.DeviceType') as mock_device_type:
                    mock_device_type.return_value.name = "WASHING_MACHINE"
                    
                    # Call the method
                    result = await dop2_client._get_program_catalog_legacy("0001")
                    
                    # Verify the correct methods were called
                    dop2_client.read_leaf.assert_any_call("0001", *dop2_client.LEAF_LEGACY_PROGRAM_LIST)
                    mock_parse_programs.assert_called_once_with(program_list_data)
                    mock_parse_options.assert_called_once_with(option_list_data)
                    mock_build_strings.assert_called_once_with(string_table_data)
                    
                    # Verify the result
                    assert result["device_type"] == "1"
                    assert len(result["programs"]) == 1
                    assert result["programs"][0]["id"] == 1
                    assert "name_id" not in result["programs"][0]  # Should be replaced with name
                    assert len(result["programs"][0]["options"]) == 1


@pytest.mark.asyncio
async def test_get_consumption_stats(dop2_client):
    """Test that get_consumption_stats calls the correct methods and returns the correct result."""
    # Mock the get_parsed method to return consumption stats data
    hours_result = HoursOfOperation(total_hours=1000)
    cycles_result = CycleCounter(total_cycles=50)
    process_data = ProcessData(energy_wh=1500, water_l=200, duration_s=3600)
    
    dop2_client.get_parsed = AsyncMock(side_effect=[
        hours_result,   # For hours of operation
        cycles_result,  # For cycle counter
        process_data    # For process data
    ])
    
    # Call the method
    result = await dop2_client.get_consumption_stats("0001")
    
    # Verify the correct methods were called
    dop2_client.get_parsed.assert_any_call("0001", *dop2_client.LEAF_HOURS_OF_OPERATION)
    dop2_client.get_parsed.assert_any_call("0001", *dop2_client.LEAF_CYCLE_COUNTER)
    dop2_client.get_parsed.assert_any_call("0001", *dop2_client.LEAF_CONSUMPTION_STATS)
    
    # Verify the result
    assert isinstance(result, ConsumptionStats)
    assert result.hours_of_operation == 1000
    assert result.cycles_completed == 50
    assert result.energy_wh_total == 1500
    assert result.water_l_total == 200


@pytest.mark.asyncio
async def test_get_setting(dop2_client):
    """Test that get_setting calls the correct methods and returns the correct result."""
    # Mock the get_parsed method to return a SFValue
    sf_value = SFValue(sf_id=100, current_value=10, minimum=0, maximum=20, default=5)
    dop2_client.get_parsed = AsyncMock(return_value=sf_value)
    
    # Call the method
    result = await dop2_client.get_setting("0001", 100)
    
    # Verify the correct methods were called
    dop2_client.get_parsed.assert_called_once_with("0001", *dop2_client.LEAF_SF_VALUE, idx1=100)
    
    # Verify the result
    assert result == sf_value


@pytest.mark.asyncio
async def test_set_setting(dop2_client):
    """Test that set_setting calls the correct methods."""
    # Mock the get_setting method to return a SFValue
    sf_value = SFValue(sf_id=100, current_value=10, minimum=0, maximum=20, default=5)
    dop2_client.get_setting = AsyncMock(return_value=sf_value)
    
    # Mock the build_sf_value_payload method
    payload = b"\x00\x64\x00\x0F"  # SF ID 100, value 15
    dop2_client.build_sf_value_payload = MagicMock(return_value=payload)
    
    # Mock the write_leaf method
    dop2_client.write_leaf = AsyncMock()
    
    # Call the method
    await dop2_client.set_setting("0001", 100, 15)
    
    # Verify the correct methods were called
    dop2_client.get_setting.assert_called_once_with("0001", 100)
    dop2_client.build_sf_value_payload.assert_called_once_with(100, 15)
    dop2_client.write_leaf.assert_called_once_with("0001", *dop2_client.LEAF_SF_VALUE, payload, idx1=100)


@pytest.mark.asyncio
async def test_set_setting_value_out_of_range(dop2_client):
    """Test that set_setting raises an error when the value is out of range."""
    # Mock the get_setting method to return a SFValue
    sf_value = SFValue(sf_id=100, current_value=10, minimum=0, maximum=20, default=5)
    dop2_client.get_setting = AsyncMock(return_value=sf_value)
    
    # Call the method with a value out of range
    with pytest.raises(ValueError, match="Value 30 outside allowed range"):
        await dop2_client.set_setting("0001", 100, 30)


def test_get_explorer(dop2_client):
    """Test that get_explorer returns a DOP2Explorer instance."""
    with patch('asyncmiele.dop2.client.DOP2Explorer') as mock_explorer_class:
        # Call the method
        explorer = dop2_client.get_explorer()
        
        # Verify the correct methods were called
        mock_explorer_class.assert_called_once_with(dop2_client)
        
        # Verify the result
        assert explorer == mock_explorer_class.return_value 