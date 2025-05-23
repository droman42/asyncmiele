"""Tests for enhanced DOP2 functionality."""

import pytest
from unittest.mock import AsyncMock, patch

from asyncmiele.dop2 import (
    DeviceCombinedState, SFValue, ConsumptionStats,
    DeviceGenerationType
)
from asyncmiele.dop2.generation import detector as generation_detector
from asyncmiele.dop2.binary import read_u16, write_u16
from asyncmiele.dop2.parser import parse_leaf
from asyncmiele.dop2.programs import build_program_selection


@pytest.fixture
def client():
    """Create a mock client for testing."""
    client = AsyncMock()
    client.dop2_read_leaf = AsyncMock()
    client.dop2_write_leaf = AsyncMock()
    client.dop2_get_parsed = AsyncMock()
    return client


@pytest.fixture
def reset_generation_detector():
    """Reset the generation detector between tests."""
    yield
    generation_detector.clear_cache()


def test_binary_read_write():
    """Test binary read/write functions."""
    # Test reading
    data = b'\x12\x34\x56\x78'
    assert read_u16(data, 0) == 0x1234
    assert read_u16(data, 2) == 0x5678
    
    # Test writing
    assert write_u16(0x1234) == b'\x12\x34'
    assert write_u16(0x5678) == b'\x56\x78'


def test_parse_device_combined_state():
    """Test parsing DeviceCombinedState."""
    payload = b'\x00\x01\x00\x02\x00\x03'
    result = parse_leaf(2, 256, payload)
    assert isinstance(result, DeviceCombinedState)
    assert result.appliance_state == 1
    assert result.operation_state == 2
    assert result.process_state == 3


def test_parse_sf_value():
    """Test parsing SFValue."""
    payload = b'\x00\x0A\x00\x14\x00\x01\x00\x64\x00\x32'
    result = parse_leaf(2, 105, payload)
    assert isinstance(result, SFValue)
    assert result.sf_id == 10
    assert result.current_value == 20
    assert result.minimum == 1
    assert result.maximum == 100
    assert result.default == 50


def test_build_program_selection():
    """Test building program selection payload."""
    # Program ID 5 with options {10: 60, 11: 1600}
    payload = build_program_selection(5, {10: 60, 11: 1600})
    
    # Check the first 10 bytes (the rest is padding)
    # Program ID (2 bytes)
    assert payload[0:2] == b'\x00\x05'
    
    # Option 10 = 60 (4 bytes: ID + value)
    assert payload[2:6] == b'\x00\x0A\x00\x3C'
    
    # Option 11 = 1600 (4 bytes: ID + value)
    assert payload[6:10] == b'\x00\x0B\x06\x40'
    
    # Check that the payload is padded to 16 bytes
    assert len(payload) == 16
    assert payload[10:] == b' ' * 6


@pytest.mark.asyncio
async def test_generation_detection(client, reset_generation_detector):
    """Test device generation detection."""
    device_id = "test_device"
    
    # No leaves registered yet, should default to DOP2
    assert generation_detector.detect_generation(device_id) == DeviceGenerationType.DOP2
    
    # Register a legacy leaf
    generation_detector.register_leaf(device_id, 14, 1570)
    assert generation_detector.detect_generation(device_id) == DeviceGenerationType.LEGACY
    
    # Register a DOP2 leaf (should override legacy)
    generation_detector.register_leaf(device_id, 2, 256)
    assert generation_detector.detect_generation(device_id) == DeviceGenerationType.DOP2
    
    # Register a semipro leaf (should override DOP2)
    generation_detector.register_leaf(device_id, 3, 1000)
    assert generation_detector.detect_generation(device_id) == DeviceGenerationType.SEMIPRO


@pytest.mark.asyncio
async def test_client_generation_detection(client, reset_generation_detector):
    """Test generation detection through client methods."""
    device_id = "test_device"
    
    # Mock successful responses for different leaves
    async def mock_read_leaf(dev_id, unit, attribute, **kwargs):
        if (unit, attribute) == (2, 256):
            generation_detector.register_leaf(dev_id, unit, attribute)
            return b'\x00\x01\x00\x02\x00\x03'
        elif (unit, attribute) == (14, 1570):
            generation_detector.register_leaf(dev_id, unit, attribute)
            return b'\x00\x01\x00\x02\x00\x03\x00\x00\x00\x00\x00\x00'
        elif (unit, attribute) == (3, 1000):
            generation_detector.register_leaf(dev_id, unit, attribute)
            return b'\x00\x01\x00\x02'
        else:
            raise Exception(f"Leaf {unit}/{attribute} not found")
    
    client.dop2_read_leaf.side_effect = mock_read_leaf
    client.detect_device_generation = AsyncMock(side_effect=lambda dev_id: generation_detector.detect_generation(dev_id))
    
    # Try reading a DOP2 leaf
    await client.dop2_read_leaf(device_id, 2, 256)
    assert generation_detector.detect_generation(device_id) == DeviceGenerationType.DOP2
    
    # Try reading a semipro leaf
    await client.dop2_read_leaf(device_id, 3, 1000)
    assert generation_detector.detect_generation(device_id) == DeviceGenerationType.SEMIPRO


@pytest.mark.asyncio
async def test_consumption_stats_parsing(client):
    """Test parsing consumption statistics."""
    device_id = "test_device"
    
    # Mock the client's dop2_get_parsed method
    async def mock_get_parsed(dev_id, unit, attribute, **kwargs):
        if (unit, attribute) == (2, 119):
            return 1000  # Hours of operation
        elif (unit, attribute) == (2, 138):
            return 50  # Cycle count
        elif (unit, attribute) == (2, 6195):
            return {"energy_wh_total": 500000, "water_l_total": 10000}
        else:
            return None
    
    client.dop2_get_parsed.side_effect = mock_get_parsed
    
    # Use the parse_consumption_stats function
    with patch('asyncmiele.dop2.parser.parse_consumption_stats') as mock_parse:
        mock_parse.return_value = ConsumptionStats(
            hours_of_operation=1000,
            cycles_completed=50,
            energy_wh_total=500000,
            water_l_total=10000
        )
        
        stats = await client.get_consumption_stats(device_id)
        
        assert stats.hours_of_operation == 1000
        assert stats.cycles_completed == 50
        assert stats.energy_wh_total == 500000
        assert stats.water_l_total == 10000
        assert stats.energy_kwh() == 500.0
        assert stats.estimate_total_cost(None) is not None 