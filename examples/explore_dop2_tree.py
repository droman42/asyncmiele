#!/usr/bin/env python3
"""
Example script demonstrating how to use the DOP2Explorer.

This script shows how to explore the DOP2 tree structure of a Miele device
and export the results to a JSON file for analysis.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

from asyncmiele import (
    ConnectionManager, DeviceProfile, MieleCredentials, 
    MieleDeviceConfig, MieleClient
)
from asyncmiele.dop2 import DOP2Explorer


async def main():
    """Main function."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python explore_dop2_tree.py <config_file> [output_file]")
        return 1
        
    config_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "dop2_tree.json"
    
    # Load configuration
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return 1
        
    # Get first device from config
    if not config.get('devices'):
        print("No devices found in configuration")
        return 1
        
    device_config = config['devices'][0]
    
    # Create device profile
    profile = DeviceProfile(
        device_id=device_config['id'],
        config=MieleDeviceConfig(host=device_config['host']),
        credentials=MieleCredentials(
            group_id=bytes.fromhex(device_config['group_id']),
            group_key=bytes.fromhex(device_config['group_key'])
        )
    )
    
    # Create connection manager
    connection_manager = ConnectionManager(retry_count=2, retry_delay=1.0)
    
    # Connect to the device and explore the DOP2 tree
    async with connection_manager:
        # Get client
        client = await connection_manager.get_client(profile.device_id, profile)
        
        # Create explorer
        explorer = DOP2Explorer(client)
        
        print(f"Connected to device {profile.device_id} at {profile.config.host}")
        print("Starting DOP2 tree exploration...")
        
        # First, try a quick exploration of known leaves only
        print("Performing quick exploration of known leaves...")
        quick_tree = await explorer.explore_device(
            profile.device_id,
            known_only=True,
            concurrency=3
        )
        
        # Print summary of quick exploration
        quick_nodes = len(quick_tree.nodes)
        quick_leaves = sum(len(node.leaves) for node in quick_tree.nodes.values())
        print(f"Quick exploration found {quick_nodes} nodes with {quick_leaves} leaves")
        
        # Ask if user wants to continue with full exploration
        response = input("Continue with full exploration? This may take several minutes. (y/N): ")
        if response.lower() not in ['y', 'yes']:
            # Export quick results and exit
            print(f"Exporting quick exploration results to {output_file}...")
            await explorer.export_tree_to_json(quick_tree, output_file)
            print(f"Results saved to {output_file}")
            return 0
            
        # Perform full exploration
        print("\nStarting full DOP2 tree exploration...")
        print("This will take several minutes. Please be patient.")
        
        # Clear cache to ensure fresh exploration
        explorer.clear_cache(profile.device_id)
        
        # Explore with more conservative parameters for thoroughness
        full_tree = await explorer.explore_device(
            profile.device_id,
            max_unit=30,
            max_attribute=20000,
            known_only=False,
            concurrency=2  # Lower concurrency to avoid overloading the device
        )
        
        # Get exploration stats
        stats = explorer.get_exploration_stats(profile.device_id)
        
        # Print summary
        full_nodes = len(full_tree.nodes)
        full_leaves = sum(len(node.leaves) for node in full_tree.nodes.values())
        duration = stats.get('duration', 0)
        
        print("\nExploration complete!")
        print(f"Found {full_nodes} nodes with {full_leaves} leaves")
        print(f"Exploration took {duration:.2f} seconds")
        
        # Export results
        print(f"Exporting results to {output_file}...")
        await explorer.export_tree_to_json(full_tree, output_file)
        print(f"Results saved to {output_file}")
        
        # Print some interesting findings
        print("\nInteresting findings:")
        
        # Show available units
        print(f"Available units: {', '.join(str(u) for u in sorted(full_tree.nodes.keys()))}")
        
        # Show leaf counts per unit
        print("\nLeaves per unit:")
        for unit in sorted(full_tree.nodes.keys()):
            leaf_count = len(full_tree.nodes[unit].leaves)
            print(f"  Unit {unit}: {leaf_count} leaves")
            
        # Show some common leaves if available
        if 2 in full_tree.nodes:
            print("\nSome common leaves in unit 2:")
            for attr in [105, 256, 293]:
                if attr in full_tree.nodes[2].leaves:
                    print(f"  Leaf 2/{attr}: {full_tree.nodes[2].leaves[attr]}")
        
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 