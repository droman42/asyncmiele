#!/usr/bin/env python3
"""
Example script demonstrating how to visualize a Miele device's DOP2 tree structure.

This script connects to a Miele device, explores its DOP2 tree structure,
and generates visualizations in both HTML and ASCII formats.
"""

import asyncio
import json
import logging
import os
import sys
from argparse import ArgumentParser
from pathlib import Path

from asyncmiele import MieleClient
from asyncmiele.config import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("dop2_visualizer_example")


async def main():
    parser = ArgumentParser(description="Visualize a Miele device's DOP2 tree structure")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("--device", type=str, help="Device ID to visualize")
    parser.add_argument("--output-dir", type=str, default="./output", help="Output directory")
    parser.add_argument("--known-only", action="store_true", help="Only explore known attributes")
    parser.add_argument("--json-file", type=str, help="Use existing JSON file instead of exploring device")
    args = parser.parse_args()

    # Create output directory if it doesn't exist
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)

    # If using existing JSON file
    if args.json_file:
        logger.info(f"Loading tree data from {args.json_file}")
        
        # Generate HTML visualization
        html_output = output_dir / "dop2_tree.html"
        logger.info(f"Generating HTML visualization: {html_output}")
        from asyncmiele.dop2.visualizer import visualize_from_json
        visualize_from_json(args.json_file, str(html_output), "html")
        
        # Generate ASCII visualization
        ascii_output = output_dir / "dop2_tree.txt"
        logger.info(f"Generating ASCII visualization: {ascii_output}")
        visualize_from_json(args.json_file, str(ascii_output), "ascii")
        
        logger.info("Visualization complete!")
        return

    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

    # Get device ID
    device_id = args.device
    if not device_id:
        # Try to get the first device from the configuration
        try:
            device_id = next(iter(config.get("devices", {})))
            logger.info(f"Using device ID from configuration: {device_id}")
        except StopIteration:
            logger.error("No device ID provided and none found in configuration")
            sys.exit(1)

    # Connect to the device
    async with MieleClient(config) as client:
        logger.info(f"Connected to Miele API")
        
        # Check if the device exists
        devices = await client.get_devices()
        if device_id not in devices:
            logger.error(f"Device {device_id} not found. Available devices: {list(devices.keys())}")
            sys.exit(1)
        
        logger.info(f"Exploring DOP2 tree for device {device_id}")
        
        # Save tree data to JSON for later use
        json_output = output_dir / "dop2_tree.json"
        logger.info(f"Saving tree data to {json_output}")
        await client.export_dop2_tree(
            device_id,
            str(json_output),
            known_only=args.known_only
        )
        
        # Generate HTML visualization
        html_output = output_dir / "dop2_tree.html"
        logger.info(f"Generating HTML visualization: {html_output}")
        await client.visualize_dop2_tree(
            device_id,
            str(html_output),
            format_type="html",
            known_only=args.known_only
        )
        
        # Generate ASCII visualization
        ascii_output = output_dir / "dop2_tree.txt"
        logger.info(f"Generating ASCII visualization: {ascii_output}")
        await client.visualize_dop2_tree(
            device_id,
            str(ascii_output),
            format_type="ascii",
            known_only=args.known_only
        )
        
        logger.info("Visualization complete!")


if __name__ == "__main__":
    asyncio.run(main()) 