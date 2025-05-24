"""
DOP2 tree explorer for comprehensive leaf exploration and analysis.

This module provides tools for systematically exploring the DOP2 tree structure
of Miele devices, discovering available leaves, and analyzing their contents.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple, Union

from .models import DOP2Tree, DOP2Node, DeviceGenerationType
from .parser import parse_leaf

logger = logging.getLogger(__name__)

# Maximum number of empty leaves before assuming no more exist
MAX_EMPTY_LEAVES = 100
MAX_ATTRIBUTE_ID = 10000

# Known DOP2 leaves organized by unit
KNOWN_LEAVES = {
    1: [2, 3, 4],  # System info, status, config
    2: [105, 119, 138, 256, 286, 293, 1584, 6195],  # Core DOP2 leaves
    3: [1000],  # Semi-pro config
    14: [1570, 1571, 2570],  # Legacy leaves
}


class DOP2Explorer:
    """Comprehensive DOP2 tree explorer.
    
    This class provides systematic exploration of the DOP2 tree structure,
    discovering available leaves and analyzing their contents.
    
    Uses a simple data provider function for leaf reading while keeping
    all DOP2 protocol knowledge internal.
    """
    
    def __init__(self, data_provider_func):
        """Initialize the explorer.
        
        Args:
            data_provider_func: Async function with signature:
                async def provider(device_id: str, unit: int, attribute: int, 
                                 idx1: int = 0, idx2: int = 0) -> Any
                Should return parsed leaf data or raise exception if leaf doesn't exist.
        """
        self._get_data = data_provider_func
        self._explored_leaves: Dict[str, Dict[Tuple[int, int], Any]] = {}
        self._failed_leaves: Dict[str, Set[Tuple[int, int]]] = {}
        self._exploration_stats: Dict[str, Dict[str, Any]] = {}
        self._cache_enabled = True
        
        
    def clear_cache(self, device_id: Optional[str] = None) -> None:
        """Clear the exploration cache.
        
        Args:
            device_id: If provided, clear only for this device; otherwise clear all
        """
        if device_id:
            if device_id in self._explored_leaves:
                del self._explored_leaves[device_id]
            if device_id in self._failed_leaves:
                del self._failed_leaves[device_id]
            if device_id in self._exploration_stats:
                del self._exploration_stats[device_id]
        else:
            self._explored_leaves.clear()
            self._failed_leaves.clear()
            self._exploration_stats.clear()
            
    def disable_cache(self) -> None:
        """Disable caching of exploration results."""
        self._cache_enabled = False
        
    def enable_cache(self) -> None:
        """Enable caching of exploration results."""
        self._cache_enabled = True
        
    async def explore_leaf(
        self, 
        device_id: str, 
        unit: int, 
        attribute: int, 
        idx1: int = 0, 
        idx2: int = 0
    ) -> Optional[Any]:
        """Explore a specific leaf in the DOP2 tree.
        
        Args:
            device_id: Device identifier
            unit: DOP2 unit number
            attribute: DOP2 attribute number
            idx1: Index 1 parameter
            idx2: Index 2 parameter
            
        Returns:
            Parsed leaf data if successful, None if the leaf doesn't exist
        """
        # Check cache first if enabled
        cache_key = (unit, attribute)
        if self._cache_enabled and device_id in self._explored_leaves and cache_key in self._explored_leaves[device_id]:
            return self._explored_leaves[device_id][cache_key]
            
        # Check if we've already tried and failed to read this leaf
        if self._cache_enabled and device_id in self._failed_leaves and cache_key in self._failed_leaves[device_id]:
            return None
            
        # Initialize cache structures if needed
        if device_id not in self._explored_leaves:
            self._explored_leaves[device_id] = {}
        if device_id not in self._failed_leaves:
            self._failed_leaves[device_id] = set()
            
        try:
            # Use DOP2LeafReader's methods
            parsed_data = await self._get_data(device_id, unit, attribute, idx1, idx2)
            
            # Cache the result if enabled
            if self._cache_enabled:
                self._explored_leaves[device_id][cache_key] = parsed_data
                
            return parsed_data
        except Exception as e:
            # Cache the failure if enabled
            if self._cache_enabled:
                self._failed_leaves[device_id].add(cache_key)
                
            logger.debug(f"Failed to read leaf {unit}/{attribute} for device {device_id}: {e}")
            return None
            
    async def explore_unit(
        self, 
        device_id: str, 
        unit: int,
        max_attribute: int = MAX_ATTRIBUTE_ID,
        known_only: bool = False,
        concurrency: int = 3
    ) -> Dict[int, Any]:
        """Explore all leaves in a specific unit.
        
        Args:
            device_id: Device identifier
            unit: DOP2 unit number
            max_attribute: Maximum attribute ID to try
            known_only: If True, only explore known leaf attributes
            concurrency: Maximum number of concurrent requests
            
        Returns:
            Dictionary mapping attribute IDs to leaf data
        """
        leaves: Dict[int, Any] = {}
        
        # Start with known leaves for this unit
        known_attributes = KNOWN_LEAVES.get(unit, [])
        
        # Create a semaphore to limit concurrency
        semaphore = asyncio.Semaphore(concurrency)
        
        # Helper function to explore a single attribute with semaphore
        async def explore_attribute(attr: int) -> Tuple[int, Optional[Any]]:
            async with semaphore:
                result = await self.explore_leaf(device_id, unit, attr)
                return attr, result
        
        # First explore known attributes
        if known_attributes:
            tasks = [explore_attribute(attr) for attr in known_attributes]
            results = await asyncio.gather(*tasks)
            
            for attr, result in results:
                if result is not None:
                    leaves[attr] = result
        
        # If we only want known leaves, return now
        if known_only:
            return leaves
            
        # Otherwise, explore all possible attributes up to max_attribute
        # Use a sliding window approach to detect ranges of empty leaves
        empty_count = 0
        attr = 1  # Start from 1
        
        while attr <= max_attribute and empty_count < MAX_EMPTY_LEAVES:
            # Create a batch of tasks
            batch_size = min(concurrency, max_attribute - attr + 1)
            tasks = [explore_attribute(attr + i) for i in range(batch_size)]
            results = await asyncio.gather(*tasks)
            
            # Process results
            all_empty = True
            for i, (explored_attr, result) in enumerate(results):
                if result is not None:
                    leaves[explored_attr] = result
                    all_empty = False
                    empty_count = 0  # Reset empty counter when we find something
                
            # Update empty counter
            if all_empty:
                empty_count += batch_size
                
            # Move to next batch
            attr += batch_size
            
        return leaves
        
    async def detect_device_generation(self, device_id: str) -> DeviceGenerationType:
        """Detect device generation based on DOP2 leaf availability.
        
        This method contains DOP2 protocol knowledge about which leaves
        are available on different device generations.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Detected device generation type
        """
        # Test for DOP2 generation (leaf 2/256 - combined state)
        try:
            await self._get_data(device_id, 2, 256)
            return DeviceGenerationType.DOP2
        except Exception:
            pass
        
        # Test for semi-pro generation (leaf 3/1000 - semi-pro config)
        try:
            await self._get_data(device_id, 3, 1000)
            return DeviceGenerationType.SEMIPRO
        except Exception:
            pass
        
        # Test for legacy generation (leaf 14/1570 - legacy program list)
        try:
            await self._get_data(device_id, 14, 1570)
            return DeviceGenerationType.LEGACY
        except Exception:
            pass
        
        # Default to DOP2 if we can't detect (most common)
        return DeviceGenerationType.DOP2
        
    async def explore_device(
        self,
        device_id: str,
        max_unit: int = 20,
        max_attribute: int = MAX_ATTRIBUTE_ID,
        known_only: bool = False,
        concurrency: int = 3
    ) -> DOP2Tree:
        """Explore the entire DOP2 tree for a device.
        
        Args:
            device_id: Device identifier
            max_unit: Maximum unit ID to try
            max_attribute: Maximum attribute ID to try
            known_only: If True, only explore known leaf attributes
            concurrency: Maximum number of concurrent requests
            
        Returns:
            DOP2Tree object containing the complete tree structure
        """
        # Initialize exploration stats
        start_time = datetime.now()
        self._exploration_stats[device_id] = {
            "start_time": start_time,
            "leaves_explored": 0,
            "leaves_found": 0,
        }
        
        # Create the tree structure
        tree = DOP2Tree(device_id=device_id)
        
        # Detect device generation using DOP2 protocol knowledge
        generation = await self.detect_device_generation(device_id)
        tree.generation = generation
        
        # First explore common units
        for unit in KNOWN_LEAVES.keys():
            if unit > max_unit:
                continue
                
            leaves = await self.explore_unit(
                device_id, 
                unit, 
                max_attribute=max_attribute, 
                known_only=known_only,
                concurrency=concurrency
            )
            
            if leaves:
                tree.nodes[unit] = DOP2Node(unit=unit, leaves=leaves)
                
        # Then explore other units up to max_unit
        for unit in range(1, max_unit + 1):
            if unit in tree.nodes or unit in KNOWN_LEAVES:
                continue
                
            leaves = await self.explore_unit(
                device_id, 
                unit, 
                max_attribute=max_attribute, 
                known_only=known_only,
                concurrency=concurrency
            )
            
            if leaves:
                tree.nodes[unit] = DOP2Node(unit=unit, leaves=leaves)
                
        # Update exploration stats
        end_time = datetime.now()
        self._exploration_stats[device_id].update({
            "end_time": end_time,
            "duration": (end_time - start_time).total_seconds(),
            "leaves_found": sum(len(node.leaves) for node in tree.nodes.values()),
        })
        
        return tree
        
    def get_exploration_stats(self, device_id: str) -> Dict[str, Any]:
        """Get statistics about the exploration process.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Dictionary with exploration statistics
        """
        return self._exploration_stats.get(device_id, {})
        
    async def export_tree_to_json(self, tree: DOP2Tree, file_path: str) -> None:
        """Export a DOP2 tree to a JSON file.
        
        Args:
            tree: DOP2Tree object to export
            file_path: Path to the output file
        """
        # Convert tree to serializable format
        serializable = {
            "device_id": tree.device_id,
            "generation": tree.generation.name if hasattr(tree, 'generation') and tree.generation else "DOP2",
            "nodes": {},
        }
        
        for unit, node in tree.nodes.items():
            serializable["nodes"][str(unit)] = {
                "unit": node.unit,
                "leaves": {},
            }
            
            for attr, data in node.leaves.items():
                # Handle different data types
                if isinstance(data, bytes):
                    # Convert bytes to hex string
                    serializable["nodes"][str(unit)]["leaves"][str(attr)] = {
                        "type": "bytes",
                        "value": data.hex(),
                    }
                elif hasattr(data, "__dict__"):
                    # Handle dataclass or similar objects
                    serializable["nodes"][str(unit)]["leaves"][str(attr)] = {
                        "type": data.__class__.__name__,
                        "value": vars(data),
                    }
                else:
                    # Handle basic types
                    serializable["nodes"][str(unit)]["leaves"][str(attr)] = {
                        "type": type(data).__name__,
                        "value": data,
                    }
        
        # Add exploration stats if available
        if tree.device_id in self._exploration_stats:
            serializable["exploration_stats"] = self._exploration_stats[tree.device_id]
            
        # Write to file
        with open(file_path, 'w') as f:
            json.dump(serializable, f, indent=2, default=str)
            
    @classmethod
    async def import_tree_from_json(cls, file_path: str) -> DOP2Tree:
        """Import a DOP2 tree from a JSON file.
        
        Args:
            file_path: Path to the input file
            
        Returns:
            DOP2Tree object
        """
        with open(file_path, 'r') as f:
            data = json.load(f)
            
        # Create tree object
        tree = DOP2Tree(
            device_id=data["device_id"]
        )
        
        # Set generation if available
        if "generation" in data:
            try:
                tree.generation = DeviceGenerationType[data["generation"]]
            except (KeyError, AttributeError):
                tree.generation = DeviceGenerationType.DOP2
        else:
            tree.generation = DeviceGenerationType.DOP2
        
        # Populate nodes and leaves
        for unit_str, node_data in data["nodes"].items():
            unit = int(unit_str)
            node = DOP2Node(unit=unit)
            
            for attr_str, leaf_data in node_data["leaves"].items():
                attr = int(attr_str)
                
                # Handle different data types based on the type field
                leaf_type = leaf_data.get("type", "unknown")
                leaf_value = leaf_data.get("value")
                
                if leaf_type == "bytes":
                    # Convert hex string back to bytes
                    node.leaves[attr] = bytes.fromhex(leaf_value)
                else:
                    # For other types, just use the value as-is
                    node.leaves[attr] = leaf_value
                    
            tree.nodes[unit] = node
            
        return tree
        
    async def compare_trees(self, tree1: DOP2Tree, tree2: DOP2Tree) -> Dict[str, Any]:
        """Compare two DOP2 trees and return the differences.
        
        Args:
            tree1: First DOP2Tree object
            tree2: Second DOP2Tree object
            
        Returns:
            Dictionary with differences between the trees
        """
        differences = {
            "device_ids": {
                "tree1": tree1.device_id,
                "tree2": tree2.device_id,
            },
            "generations": {
                "tree1": tree1.generation.name if hasattr(tree1, 'generation') and tree1.generation else "DOP2",
                "tree2": tree2.generation.name if hasattr(tree2, 'generation') and tree2.generation else "DOP2",
            },
            "units": {
                "only_in_tree1": [u for u in tree1.nodes if u not in tree2.nodes],
                "only_in_tree2": [u for u in tree2.nodes if u not in tree1.nodes],
                "common": [u for u in tree1.nodes if u in tree2.nodes],
            },
            "leaves": {
                "only_in_tree1": {},
                "only_in_tree2": {},
                "common": {},
                "different_values": {},
            },
        }
        
        # Compare leaves in common units
        for unit in differences["units"]["common"]:
            node1 = tree1.nodes[unit]
            node2 = tree2.nodes[unit]
            
            # Leaves only in tree1
            only_in_tree1 = [a for a in node1.leaves if a not in node2.leaves]
            if only_in_tree1:
                differences["leaves"]["only_in_tree1"][unit] = only_in_tree1
                
            # Leaves only in tree2
            only_in_tree2 = [a for a in node2.leaves if a not in node1.leaves]
            if only_in_tree2:
                differences["leaves"]["only_in_tree2"][unit] = only_in_tree2
                
            # Common leaves
            common = [a for a in node1.leaves if a in node2.leaves]
            if common:
                differences["leaves"]["common"][unit] = common
                
            # Leaves with different values
            different_values = []
            for attr in common:
                val1 = node1.leaves[attr]
                val2 = node2.leaves[attr]
                
                # Compare values (simple equality check)
                if val1 != val2:
                    different_values.append(attr)
                    
            if different_values:
                differences["leaves"]["different_values"][unit] = different_values
                
        return differences


# Global instance for shared use - can be initialized with None
explorer: Optional[DOP2Explorer] = None

def set_client(client) -> None:
    """Set the client for the global explorer instance.
    
    Args:
        client: Any object with a get_parsed_dop2_leaf method
    """
    global explorer
    
    # Create a simple data provider function from the client
    async def data_provider(device_id: str, unit: int, attribute: int, idx1: int = 0, idx2: int = 0):
        return await client.get_parsed_dop2_leaf(device_id, unit, attribute, idx1, idx2)
    
    explorer = DOP2Explorer(data_provider)


def create_explorer_with_client(miele_client) -> DOP2Explorer:
    """Create a DOP2Explorer using a MieleClient.
    
    Args:
        miele_client: MieleClient instance with get_parsed_dop2_leaf method
        
    Returns:
        DOP2Explorer instance
    """
    # Create a simple data provider function
    async def data_provider(device_id: str, unit: int, attribute: int, idx1: int = 0, idx2: int = 0):
        return await miele_client.get_parsed_dop2_leaf(device_id, unit, attribute, idx1, idx2)
    
    return DOP2Explorer(data_provider)


def create_mock_explorer(mock_data: Dict[Tuple[int, int], Any] = None) -> DOP2Explorer:
    """Create a DOP2Explorer with mock data for testing.
    
    Args:
        mock_data: Dictionary mapping (unit, attribute) -> parsed_data
        
    Returns:
        DOP2Explorer instance with mock data
    """
    mock_data = mock_data or {}
    
    async def mock_data_provider(device_id: str, unit: int, attribute: int, idx1: int = 0, idx2: int = 0):
        key = (unit, attribute)
        if key in mock_data:
            return mock_data[key]
        raise Exception(f"Mock leaf {unit}/{attribute} not found")
    
    return DOP2Explorer(mock_data_provider) 