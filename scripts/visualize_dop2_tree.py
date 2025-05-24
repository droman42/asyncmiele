#!/usr/bin/env python3
"""
DOP2 Tree Visualization Script.

This script provides a command-line interface for visualizing the DOP2 tree structure
of Miele devices. It can generate HTML or ASCII representations of the tree.
"""

import asyncio
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from asyncmiele import (
    ConnectionManager, DeviceProfile, MieleCredentials, 
    MieleClient
)
from asyncmiele.dop2 import (
    DeviceGenerationType, DOP2Tree, DOP2Explorer, DOP2Visualizer,
    visualize_tree, visualize_from_json
)
from asyncmiele.exceptions.connection import ConnectionLostError


async def visualize_device_tree(
    profile: DeviceProfile,
    output_file: str,
    format_type: str = 'html',
    max_unit: int = 20,
    max_attribute: int = 10000,
    known_only: bool = False,
    concurrency: int = 3,
    timeout: float = 10.0,
    explore_first: bool = True,
    json_file: Optional[str] = None
) -> Dict[str, Any]:
    """Visualize the DOP2 tree of a device.
    
    Args:
        profile: Device profile with connection information
        output_file: Path to save the visualization
        format_type: Type of visualization to generate ('html' or 'ascii')
        max_unit: Maximum unit ID to explore
        max_attribute: Maximum attribute ID to explore
        known_only: If True, only explore known leaf attributes
        concurrency: Maximum number of concurrent requests
        timeout: Timeout for API requests in seconds
        explore_first: If True, explore the device first; otherwise use existing JSON
        json_file: Path to JSON file with tree data (if not exploring)
        
    Returns:
        Dictionary with visualization results
    """
    device_id = profile.device_id
    host = profile.host
    
    # If using existing JSON, visualize directly
    if not explore_first and json_file:
        print(f"Visualizing DOP2 tree from JSON file: {json_file}")
        visualize_from_json(json_file, output_file, format_type)
        print(f"Visualization saved to {output_file}")
        return {"success": True}
    
    # Create connection manager
    connection_manager = ConnectionManager(retry_count=2, retry_delay=1.0)
    
    # Start connection manager
    async with connection_manager:
        try:
            print(f"Connecting to device {device_id} at {host}...")
            
            # Get client from manager
            client = await connection_manager.get_client(device_id, profile)
            client.timeout = timeout
            
            # Create explorer
            explorer = DOP2Explorer(client)
            
            # Detect device generation first
            print("Detecting device generation...")
            generation = await client.detect_device_generation(device_id)
            print(f"Detected generation: {generation.name}")
            
            # Start exploration
            print(f"Starting DOP2 tree exploration (max unit: {max_unit}, max attribute: {max_attribute})...")
            print(f"Using concurrency level: {concurrency}")
            
            if known_only:
                print("Exploring only known leaves")
            else:
                print("Performing full exploration (this may take a while)")
                
            tree = await explorer.explore_device(
                device_id,
                max_unit=max_unit,
                max_attribute=max_attribute,
                known_only=known_only,
                concurrency=concurrency
            )
            
            # Get exploration stats
            stats = explorer.get_exploration_stats(device_id)
            
            # Print summary
            total_nodes = len(tree.nodes)
            total_leaves = sum(len(node.leaves) for node in tree.nodes.values())
            
            print("\nExploration complete!")
            print(f"Found {total_nodes} nodes with {total_leaves} leaves")
            print(f"Exploration took {stats.get('duration', 0):.2f} seconds")
            
            # Save JSON if requested
            if json_file:
                print(f"Saving tree data to {json_file}...")
                await explorer.export_tree_to_json(tree, json_file)
                print(f"Tree data saved to {json_file}")
            
            # Visualize tree
            print(f"Generating {format_type.upper()} visualization...")
            visualizer = DOP2Visualizer(tree)
            
            if format_type.lower() == 'html':
                visualizer.save_html(output_file)
            else:
                visualizer.save_ascii(output_file)
                
            print(f"Visualization saved to {output_file}")
                
            # Return results
            return {
                "device_id": device_id,
                "generation": generation.name,
                "nodes": total_nodes,
                "leaves": total_leaves,
                "stats": stats,
                "output_file": output_file,
                "format": format_type
            }
                
        except ConnectionLostError as e:
            print(f"Connection lost: {e}")
            return {"error": str(e)}
        except Exception as e:
            print(f"Error during visualization: {e}")
            return {"error": str(e)}


def load_profile(config_file: str, device_id: Optional[str] = None) -> Optional[DeviceProfile]:
    """Load a device profile from a configuration file.
    
    Args:
        config_file: Path to configuration file
        device_id: Specific device ID to load, or None to load the first device
        
    Returns:
        DeviceProfile or None if not found
    """
    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
            
        devices = config_data.get('devices', [])
        if not devices:
            print("No devices found in configuration file.")
            return None
            
        # Find the requested device or use the first one
        device_config = None
        if device_id:
            for dev in devices:
                if dev.get('id') == device_id:
                    device_config = dev
                    break
            if not device_config:
                print(f"Device ID {device_id} not found in configuration file.")
                return None
        else:
            device_config = devices[0]
            
        # Create credentials
        credentials = MieleCredentials(
            group_id=bytes.fromhex(device_config['group_id']),
            group_key=bytes.fromhex(device_config['group_key'])
        )
        
        # Create profile
        profile = DeviceProfile(
            device_id=device_config['id'],
            host=device_config['host'],
            credentials=credentials
        )
        
        return profile
            
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="DOP2 Tree Visualization for Miele Devices"
    )
    parser.add_argument(
        "--config", type=str,
        help="Path to configuration file with device profiles"
    )
    parser.add_argument(
        "--device-id", type=str,
        help="Device ID to visualize"
    )
    parser.add_argument(
        "--output", type=str, default="dop2_tree_visualization",
        help="Path to save the visualization (without extension)"
    )
    parser.add_argument(
        "--format", type=str, choices=['html', 'ascii'], default='html',
        help="Format of the visualization (html or ascii)"
    )
    parser.add_argument(
        "--max-unit", type=int, default=20,
        help="Maximum unit ID to explore"
    )
    parser.add_argument(
        "--max-attribute", type=int, default=10000,
        help="Maximum attribute ID to explore"
    )
    parser.add_argument(
        "--known-only", action="store_true",
        help="Only explore known leaf attributes"
    )
    parser.add_argument(
        "--concurrency", type=int, default=3,
        help="Maximum number of concurrent requests"
    )
    parser.add_argument(
        "--timeout", type=float, default=10.0,
        help="Timeout for API requests in seconds"
    )
    parser.add_argument(
        "--json-file", type=str,
        help="Path to JSON file with tree data (for loading or saving)"
    )
    parser.add_argument(
        "--no-explore", action="store_true",
        help="Skip exploration and use existing JSON file"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Check if we need to explore or just visualize existing JSON
    if args.no_explore:
        if not args.json_file:
            print("Error: --no-explore requires --json-file")
            return 1
            
        # Add extension to output file
        output_file = f"{args.output}.{args.format}"
        
        # Visualize from JSON directly
        visualize_from_json(args.json_file, output_file, args.format)
        print(f"Visualization saved to {output_file}")
        return 0
    
    # Check if we need to load a profile
    if not args.config:
        print("Error: --config is required unless --no-explore is specified")
        return 1
    
    # Load profile from config
    profile = load_profile(args.config, args.device_id)
    if not profile:
        return 1
    
    # Add extension to output file
    output_file = f"{args.output}.{args.format}"
    
    # Run visualization
    result = asyncio.run(visualize_device_tree(
        profile,
        output_file=output_file,
        format_type=args.format,
        max_unit=args.max_unit,
        max_attribute=args.max_attribute,
        known_only=args.known_only,
        concurrency=args.concurrency,
        timeout=args.timeout,
        explore_first=not args.no_explore,
        json_file=args.json_file
    ))
    
    if "error" in result:
        return 1
        
    return 0


if __name__ == "__main__":
    sys.exit(main()) 