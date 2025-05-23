"""Tests for DOP2Explorer functionality."""

import pytest
import json
import tempfile
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from asyncmiele.dop2 import DeviceGenerationType
from asyncmiele.dop2.models import DOP2Tree, DOP2Node
from asyncmiele.dop2.explorer import DOP2Explorer


@pytest.fixture
def client():
    """Create a mock client for testing."""
    client = AsyncMock()
    client.dop2_read_leaf = AsyncMock()
    client.detect_device_generation = AsyncMock(return_value=DeviceGenerationType.DOP2)
    return client


@pytest.fixture
def explorer(client):
    """Create a DOP2Explorer with a mock client."""
    return DOP2Explorer(client)


@pytest.mark.asyncio
async def test_explore_leaf(explorer, client):
    """Test exploring a single leaf."""
    device_id = "test_device"
    unit = 2
    attribute = 256
    
    # Mock the client to return some test data
    test_data = b'\x00\x01\x00\x02\x00\x03'
    client.dop2_read_leaf.return_value = test_data
    
    # Explore the leaf
    result = await explorer.explore_leaf(device_id, unit, attribute)
    
    # Check that the client was called correctly
    client.dop2_read_leaf.assert_called_once_with(device_id, unit, attribute, idx1=0, idx2=0)
    
    # Check that the result is not None (actual parsing is tested elsewhere)
    assert result is not None


@pytest.mark.asyncio
async def test_explore_leaf_caching(explorer, client):
    """Test that leaf exploration results are cached."""
    device_id = "test_device"
    unit = 2
    attribute = 256
    
    # Mock the client to return some test data
    test_data = b'\x00\x01\x00\x02\x00\x03'
    client.dop2_read_leaf.return_value = test_data
    
    # Explore the leaf twice
    result1 = await explorer.explore_leaf(device_id, unit, attribute)
    result2 = await explorer.explore_leaf(device_id, unit, attribute)
    
    # Check that the client was called only once
    client.dop2_read_leaf.assert_called_once()
    
    # Check that both results are the same
    assert result1 is result2


@pytest.mark.asyncio
async def test_explore_leaf_failure(explorer, client):
    """Test handling of leaf exploration failures."""
    device_id = "test_device"
    unit = 2
    attribute = 999  # Non-existent leaf
    
    # Mock the client to raise an exception
    client.dop2_read_leaf.side_effect = Exception("Leaf not found")
    
    # Explore the leaf
    result = await explorer.explore_leaf(device_id, unit, attribute)
    
    # Check that the result is None
    assert result is None
    
    # Check that the failure is cached
    assert (unit, attribute) in explorer._failed_leaves[device_id]


@pytest.mark.asyncio
async def test_explore_unit(explorer, client):
    """Test exploring a unit with multiple leaves."""
    device_id = "test_device"
    unit = 2
    
    # Mock the client to return data for some leaves and fail for others
    async def mock_explore_leaf(dev_id, u, attr, idx1=0, idx2=0):
        if u == unit and attr in [105, 256]:
            return f"Leaf {attr} data"
        else:
            return None
    
    # Replace the explore_leaf method with our mock
    explorer.explore_leaf = AsyncMock(side_effect=mock_explore_leaf)
    
    # Explore the unit (only known leaves)
    leaves = await explorer.explore_unit(device_id, unit, known_only=True)
    
    # Check that we found the expected leaves
    assert 105 in leaves
    assert 256 in leaves
    assert len(leaves) == 2


@pytest.mark.asyncio
async def test_explore_device(explorer, client):
    """Test exploring a complete device."""
    device_id = "test_device"
    
    # Mock the explore_unit method to return some test data
    async def mock_explore_unit(dev_id, unit, **kwargs):
        if unit == 1:
            return {2: "System info"}
        elif unit == 2:
            return {105: "SF Value", 256: "Combined state"}
        elif unit == 14:
            return {1570: "Program list"}
        else:
            return {}
    
    explorer.explore_unit = AsyncMock(side_effect=mock_explore_unit)
    
    # Explore the device
    tree = await explorer.explore_device(device_id, known_only=True)
    
    # Check that the tree has the expected structure
    assert tree.device_id == device_id
    assert tree.generation == DeviceGenerationType.DOP2
    assert 1 in tree.nodes
    assert 2 in tree.nodes
    assert 14 in tree.nodes
    assert len(tree.nodes) == 3


@pytest.mark.asyncio
async def test_export_import_tree(explorer):
    """Test exporting and importing a DOP2 tree to/from JSON."""
    # Create a test tree
    tree = DOP2Tree(
        device_id="test_device",
        generation=DeviceGenerationType.DOP2
    )
    
    # Add some nodes and leaves
    tree.nodes[1] = DOP2Node(unit=1, leaves={
        2: "System info"
    })
    
    tree.nodes[2] = DOP2Node(unit=2, leaves={
        105: "SF Value",
        256: "Combined state",
        293: b'\x07\xe5\x08\x1e\x0f\x2a\x1e'  # Binary data
    })
    
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        # Export the tree
        await explorer.export_tree_to_json(tree, tmp_path)
        
        # Check that the file exists and has content
        assert Path(tmp_path).exists()
        assert Path(tmp_path).stat().st_size > 0
        
        # Import the tree
        imported_tree = await DOP2Explorer.import_tree_from_json(tmp_path)
        
        # Check that the imported tree has the same structure
        assert imported_tree.device_id == tree.device_id
        assert imported_tree.generation == tree.generation
        assert set(imported_tree.nodes.keys()) == set(tree.nodes.keys())
        
        # Check that unit 2 has the expected leaves
        assert 105 in imported_tree.nodes[2].leaves
        assert 256 in imported_tree.nodes[2].leaves
        assert 293 in imported_tree.nodes[2].leaves
        
    finally:
        # Clean up the temporary file
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_compare_trees(explorer):
    """Test comparing two DOP2 trees."""
    # Create two test trees with some differences
    tree1 = DOP2Tree(
        device_id="device1",
        generation=DeviceGenerationType.DOP2
    )
    
    tree1.nodes[1] = DOP2Node(unit=1, leaves={
        2: "System info"
    })
    
    tree1.nodes[2] = DOP2Node(unit=2, leaves={
        105: "SF Value",
        256: "Combined state",
        293: "DateTime"
    })
    
    tree2 = DOP2Tree(
        device_id="device2",
        generation=DeviceGenerationType.LEGACY
    )
    
    tree2.nodes[1] = DOP2Node(unit=1, leaves={
        2: "System info"
    })
    
    tree2.nodes[2] = DOP2Node(unit=2, leaves={
        105: "Different SF Value",
        256: "Combined state"
    })
    
    tree2.nodes[14] = DOP2Node(unit=14, leaves={
        1570: "Program list"
    })
    
    # Compare the trees
    diff = await explorer.compare_trees(tree1, tree2)
    
    # Check the differences
    assert diff["generations"]["tree1"] == "DOP2"
    assert diff["generations"]["tree2"] == "LEGACY"
    
    assert 14 in diff["units"]["only_in_tree2"]
    assert 2 in diff["units"]["common"]
    
    assert 293 in diff["leaves"]["only_in_tree1"][2]
    assert 105 in diff["leaves"]["different_values"][2] 