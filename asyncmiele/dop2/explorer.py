"""DOP2 tree explorer for Miele devices.

This module provides functionality to recursively explore the DOP2 tree structure
of Miele appliances. It can discover all available nodes and leaves, and build
a complete map of the device's DOP2 structure.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Set, Any, Optional, Tuple, cast

from .models import (
    DOP2Tree, DOP2Node, DeviceGenerationType
)
from .generation import detector
from .parser import parse_leaf

logger = logging.getLogger(__name__)

# Common units to explore first (based on observed patterns)
COMMON_UNITS = [1, 2, 3, 14]

# Known leaf attributes for each unit (to try first before brute force)
KNOWN_LEAVES = {
    1: [2, 3, 4],                # System leaves
    2: [105, 119, 138, 256, 286, 293, 1584, 6195],  # Core DOP2 leaves
    3: [1000],                   # Semi-pro specific leaves
    14: [1570, 1571, 2570]       # Legacy leaves
}

# Maximum attribute ID to try during brute force exploration
MAX_ATTRIBUTE_ID = 10000

# Maximum number of consecutive empty leaves before stopping exploration
MAX_EMPTY_LEAVES = 50


class DOP2Explorer:
    """Explorer for DOP2 tree structures.
    
    This class provides functionality to recursively explore the DOP2 tree structure
    of Miele appliances. It can discover all available nodes and leaves, and build
    a complete map of the device's DOP2 structure.
    """
    
    def __init__(self, client_or_dop2client: Any):
        """Initialize the explorer with a client.
        
        Args:
            client_or_dop2client: MieleClient or DOP2Client instance
        """
        # Handle None as a special case for the global instance
        if client_or_dop2client is None:
            self.dop2_client = None
        # Check if it's already a DOP2Client
        elif hasattr(client_or_dop2client, 'read_leaf'):
            self.dop2_client = client_or_dop2client
        else:
            # It's a MieleClient, get a DOP2Client from it
            self.dop2_client = client_or_dop2client.get_dop2_client()
            
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
        # Check if dop2_client is initialized
        if self.dop2_client is None:
            raise RuntimeError("DOP2Explorer not initialized with a client")
            
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
            # Try to read the leaf
            raw_data = await self.dop2_client.read_leaf(device_id, unit, attribute, idx1=idx1, idx2=idx2)
            
            # Parse the leaf data
            parsed_data = parse_leaf(unit, attribute, raw_data)
            
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
        start_time = time.time()
        self._exploration_stats[device_id] = {
            "start_time": start_time,
            "leaves_explored": 0,
            "leaves_found": 0,
        }
        
        # Create the tree structure
        tree = DOP2Tree(device_id=device_id)
        
        # Detect device generation
        generation = await self.dop2_client.detect_device_generation(device_id)
        tree.generation = generation
        
        # First explore common units
        for unit in COMMON_UNITS:
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
            if unit in tree.nodes or unit in COMMON_UNITS:
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
        end_time = time.time()
        self._exploration_stats[device_id].update({
            "end_time": end_time,
            "duration": end_time - start_time,
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
            "generation": tree.generation.name,
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
            device_id=data["device_id"],
            generation=DeviceGenerationType[data["generation"]]
        )
        
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
                "tree1": tree1.generation.name,
                "tree2": tree2.generation.name,
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


# Global instance for shared use
explorer = DOP2Explorer(None)

def set_client(client: Any) -> None:
    """Set the client for the global explorer instance.
    
    Args:
        client: MieleClient or DOP2Client instance
    """
    global explorer
    explorer = DOP2Explorer(client) 