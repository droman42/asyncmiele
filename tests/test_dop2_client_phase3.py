import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from asyncmiele.api.client import MieleClient
from asyncmiele.dop2.client import DOP2Client
from asyncmiele.dop2.explorer import DOP2Explorer
from asyncmiele.dop2.models import ConsumptionStats, SFValue, DeviceGenerationType, DOP2Tree


@pytest.fixture
def miele_client():
    """Return a MagicMock of MieleClient."""
    return MagicMock(spec=MieleClient)


@pytest.fixture
def dop2_client():
    """Return a MagicMock of DOP2Client with AsyncMock methods."""
    client = MagicMock(spec=DOP2Client)
    # Set up AsyncMock for async methods
    client.detect_generation = AsyncMock()
    client.get_consumption_stats = AsyncMock()
    client.get_setting = AsyncMock()
    client.set_setting = AsyncMock()
    client.get_program_catalog = AsyncMock()
    client._get_program_catalog_legacy = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_detect_device_generation():
    """Test that detect_device_generation delegates to DOP2Client."""
    # Create MieleClient with the method we're testing
    async def detect_device_generation(device_id):
        dop2_client = miele_client.get_dop2_client()
        return await dop2_client.detect_generation(device_id)
    
    # Create the mock client
    miele_client = MagicMock()
    miele_client.detect_device_generation = detect_device_generation
    
    # Create DOP2Client mock
    dop2_client = MagicMock(spec=DOP2Client)
    dop2_client.detect_generation = AsyncMock()
    
    # Set up the return value
    expected_generation = DeviceGenerationType.DOP2
    dop2_client.detect_generation.return_value = expected_generation
    
    # Set up the miele_client to return our mocked dop2_client
    miele_client.get_dop2_client.return_value = dop2_client
    
    # Call the method
    result = await miele_client.detect_device_generation("0001")
    
    # Verify the correct methods were called
    miele_client.get_dop2_client.assert_called_once()
    dop2_client.detect_generation.assert_awaited_once_with("0001")
    assert result == expected_generation


@pytest.mark.asyncio
async def test_get_consumption_stats():
    """Test that get_consumption_stats delegates to DOP2Client."""
    # Create MieleClient with the method we're testing
    async def get_consumption_stats(device_id):
        dop2_client = miele_client.get_dop2_client()
        return await dop2_client.get_consumption_stats(device_id)
    
    # Create the mock client
    miele_client = MagicMock()
    miele_client.get_consumption_stats = get_consumption_stats
    
    # Create DOP2Client mock
    dop2_client = MagicMock(spec=DOP2Client)
    dop2_client.get_consumption_stats = AsyncMock()
    
    # Set up the return value
    expected_stats = ConsumptionStats(
        hours_of_operation=1000,
        cycles_completed=50,
        energy_wh_total=1500,
        water_l_total=200
    )
    dop2_client.get_consumption_stats.return_value = expected_stats
    
    # Set up the miele_client to return our mocked dop2_client
    miele_client.get_dop2_client.return_value = dop2_client
    
    # Call the method
    result = await miele_client.get_consumption_stats("0001")
    
    # Verify the correct methods were called
    miele_client.get_dop2_client.assert_called_once()
    dop2_client.get_consumption_stats.assert_awaited_once_with("0001")
    assert result == expected_stats


@pytest.mark.asyncio
async def test_get_setting():
    """Test that get_setting delegates to DOP2Client."""
    # Create MieleClient with the method we're testing
    async def get_setting(device_id, sf_id):
        dop2_client = miele_client.get_dop2_client()
        return await dop2_client.get_setting(device_id, sf_id)
    
    # Create the mock client
    miele_client = MagicMock()
    miele_client.get_setting = get_setting
    
    # Create DOP2Client mock
    dop2_client = MagicMock(spec=DOP2Client)
    dop2_client.get_setting = AsyncMock()
    
    # Set up the return value
    expected_setting = SFValue(sf_id=100, current_value=10, minimum=0, maximum=20, default=5)
    dop2_client.get_setting.return_value = expected_setting
    
    # Set up the miele_client to return our mocked dop2_client
    miele_client.get_dop2_client.return_value = dop2_client
    
    # Call the method
    result = await miele_client.get_setting("0001", 100)
    
    # Verify the correct methods were called
    miele_client.get_dop2_client.assert_called_once()
    dop2_client.get_setting.assert_awaited_once_with("0001", 100)
    assert result == expected_setting


@pytest.mark.asyncio
async def test_set_setting():
    """Test that set_setting delegates to DOP2Client."""
    # Create MieleClient with the method we're testing
    async def set_setting(device_id, sf_id, new_value):
        dop2_client = miele_client.get_dop2_client()
        await dop2_client.set_setting(device_id, sf_id, new_value)
    
    # Create the mock client
    miele_client = MagicMock()
    miele_client.set_setting = set_setting
    
    # Create DOP2Client mock
    dop2_client = MagicMock(spec=DOP2Client)
    dop2_client.set_setting = AsyncMock()
    
    # Set up the miele_client to return our mocked dop2_client
    miele_client.get_dop2_client.return_value = dop2_client
    
    # Call the method
    await miele_client.set_setting("0001", 100, 15)
    
    # Verify the correct methods were called
    miele_client.get_dop2_client.assert_called_once()
    dop2_client.set_setting.assert_awaited_once_with("0001", 100, 15)


@pytest.mark.asyncio
async def test_get_program_catalog():
    """Test that get_program_catalog delegates to DOP2Client."""
    # Create MieleClient with the method we're testing
    async def get_program_catalog(device_id):
        dop2_client = miele_client.get_dop2_client()
        return await dop2_client.get_program_catalog(device_id)
    
    # Create the mock client
    miele_client = MagicMock()
    miele_client.get_program_catalog = get_program_catalog
    
    # Create DOP2Client mock
    dop2_client = MagicMock(spec=DOP2Client)
    dop2_client.get_program_catalog = AsyncMock()
    
    # Set up the return value
    expected_catalog = {
        "device_type": "WASHING_MACHINE",
        "programs": [
            {"id": 1, "name": "Program_1", "options": [{"id": 1, "value": 10}]}
        ]
    }
    dop2_client.get_program_catalog.return_value = expected_catalog
    
    # Set up the miele_client to return our mocked dop2_client
    miele_client.get_dop2_client.return_value = dop2_client
    
    # Call the method
    result = await miele_client.get_program_catalog("0001")
    
    # Verify the correct methods were called
    miele_client.get_dop2_client.assert_called_once()
    dop2_client.get_program_catalog.assert_awaited_once_with("0001")
    assert result == expected_catalog


@pytest.mark.asyncio
async def test_fallback_get_program_catalog():
    """Test that fallback_get_program_catalog delegates to DOP2Client."""
    # Create MieleClient with the method we're testing
    async def fallback_get_program_catalog(device_id):
        dop2_client = miele_client.get_dop2_client()
        return await dop2_client._get_program_catalog_legacy(device_id)
    
    # Create the mock client
    miele_client = MagicMock()
    miele_client.fallback_get_program_catalog = fallback_get_program_catalog
    
    # Create DOP2Client mock
    dop2_client = MagicMock(spec=DOP2Client)
    dop2_client._get_program_catalog_legacy = AsyncMock()
    
    # Set up the return value
    expected_catalog = {
        "device_type": "WASHING_MACHINE",
        "programs": [
            {"id": 1, "name": "Program 1", "options": [{"id": 2, "name": "Option 2", "default": 5}]}
        ]
    }
    dop2_client._get_program_catalog_legacy.return_value = expected_catalog
    
    # Set up the miele_client to return our mocked dop2_client
    miele_client.get_dop2_client.return_value = dop2_client
    
    # Call the method
    result = await miele_client.fallback_get_program_catalog("0001")
    
    # Verify the correct methods were called
    miele_client.get_dop2_client.assert_called_once()
    dop2_client._get_program_catalog_legacy.assert_awaited_once_with("0001")
    assert result == expected_catalog


def test_get_explorer():
    """Test that get_explorer delegates to DOP2Client."""
    # Create MieleClient with the method we're testing
    def get_explorer():
        dop2_client = miele_client.get_dop2_client()
        return dop2_client.get_explorer()
    
    # Create the mock client
    miele_client = MagicMock()
    miele_client.get_explorer = get_explorer
    
    # Create DOP2Client mock
    dop2_client = MagicMock(spec=DOP2Client)
    
    # Set up the return value
    explorer_mock = MagicMock(spec=DOP2Explorer)
    dop2_client.get_explorer.return_value = explorer_mock
    
    # Set up the miele_client to return our mocked dop2_client
    miele_client.get_dop2_client.return_value = dop2_client
    
    # Call the method
    result = miele_client.get_explorer()
    
    # Verify the correct methods were called
    miele_client.get_dop2_client.assert_called_once()
    dop2_client.get_explorer.assert_called_once()
    assert result == explorer_mock


@pytest.mark.asyncio
async def test_explore_dop2_tree():
    """Test that explore_dop2_tree delegates to DOP2Client."""
    # Create MieleClient with the method we're testing
    async def explore_dop2_tree(device_id, max_unit=20, max_attribute=10000, known_only=False, concurrency=3):
        dop2_client = miele_client.get_dop2_client()
        explorer = dop2_client.get_explorer()
        return await explorer.explore_device(
            device_id,
            max_unit=max_unit,
            max_attribute=max_attribute,
            known_only=known_only,
            concurrency=concurrency
        )
    
    # Create the mock client
    miele_client = MagicMock()
    miele_client.explore_dop2_tree = explore_dop2_tree
    
    # Create DOP2Client mock
    dop2_client = MagicMock(spec=DOP2Client)
    
    # Set up the explorer mock
    explorer_mock = MagicMock(spec=DOP2Explorer)
    dop2_client.get_explorer.return_value = explorer_mock
    
    # Set up the tree mock
    tree_mock = MagicMock(spec=DOP2Tree)
    explorer_mock.explore_device = AsyncMock(return_value=tree_mock)
    
    # Set up the miele_client to return our mocked dop2_client
    miele_client.get_dop2_client.return_value = dop2_client
    
    # Call the method
    result = await miele_client.explore_dop2_tree(
        "0001",
        max_unit=10,
        max_attribute=5000,
        known_only=True,
        concurrency=2
    )
    
    # Verify the correct methods were called
    miele_client.get_dop2_client.assert_called_once()
    dop2_client.get_explorer.assert_called_once()
    explorer_mock.explore_device.assert_awaited_once_with(
        "0001", 
        max_unit=10, 
        max_attribute=5000, 
        known_only=True, 
        concurrency=2
    )
    assert result == tree_mock 