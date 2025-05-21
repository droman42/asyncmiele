#!/usr/bin/env python3
"""
Script for obtaining Miele device credentials and saving them to a JSON file.

This script can either discover devices on the network or connect to a device
with a known IP address. It then registers with the device and saves the
credentials to a JSON file.

Usage:
    # Discover devices and let user select one:
    python scripts/get_device_credentials.py --output credentials.json

    # Connect directly to a device with known IP:
    python scripts/get_device_credentials.py --host 192.168.1.123 --output credentials.json
"""

import asyncio
import argparse
import json
import os
import sys
from typing import Dict, List, Optional, Tuple, Any

from asyncmiele import easy_setup
from asyncmiele.utils.discovery import discover_devices
from asyncmiele.exceptions import MieleException


async def discover_miele_devices() -> List[Dict[str, Any]]:
    """
    Discover Miele devices on the local network.
    
    Returns:
        List of dictionaries with device information
    """
    print("Searching for Miele devices on the local network...")
    print("This may take a few seconds...")
    
    devices = await discover_devices(timeout=5.0)
    
    if not devices:
        print("\nNo Miele devices found.")
        print("Make sure your devices are connected to the network and try again.")
        return []
        
    print(f"\nFound {len(devices)} Miele device(s):")
    
    for idx, device in enumerate(devices, 1):
        print(f"\n[{idx}] Device:")
        print(f"  IP Address: {device['host']}")
        
        if 'server' in device:
            print(f"  Server: {device['server']}")
            
        if 'location' in device:
            print(f"  Device URL: {device['location']}")
    
    return devices


async def register_with_device(host: str) -> Optional[Dict[str, str]]:
    """
    Register with a Miele device and return the credentials.
    
    Args:
        host: Device hostname or IP address
        
    Returns:
        Dictionary with device credentials or None if registration failed
    """
    try:
        print(f"\nAttempting to register with Miele device at {host}...")
        print("Make sure the device is in commissioning/registration mode.")
        print("This typically means it's connected to WiFi but not yet set up in the Miele app.")
        
        device_id, group_id, group_key = await easy_setup(host)
        
        print("\nRegistration successful!")
        print(f"\nDevice ID: {device_id}")
        print(f"Group ID: {group_id}")
        print(f"Group Key: {group_key}")
        
        return {
            "host": host,
            "device_id": device_id,
            "group_id": group_id,
            "group_key": group_key
        }
        
    except MieleException as e:
        print(f"Error: {e}")
        print("\nRegistration failed. Make sure the device is in commissioning mode and is reachable.")
        return None


def save_credentials_to_file(credentials: Dict[str, str], output_file: str) -> None:
    """
    Save credentials to a JSON file.
    
    Args:
        credentials: Dictionary with device credentials
        output_file: Path to the output file
    """
    # Create directory if it doesn't exist
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Save credentials to file
    with open(output_file, 'w') as f:
        json.dump(credentials, f, indent=2)
        
    print(f"\nCredentials saved to {output_file}")
    print("Keep this file secure as it contains sensitive information.")


async def main(args: argparse.Namespace) -> None:
    """
    Main function to get device credentials and save them to a file.
    
    Args:
        args: Command-line arguments
    """
    credentials = None
    
    # If host is provided, register directly
    if args.host:
        credentials = await register_with_device(args.host)
    else:
        # Otherwise discover devices and let user select one
        devices = await discover_miele_devices()
        
        if not devices:
            sys.exit(1)
        
        while True:
            try:
                selection = input("\nEnter the number of the device to register with [1]: ") or "1"
                idx = int(selection) - 1
                
                if 0 <= idx < len(devices):
                    selected_device = devices[idx]
                    credentials = await register_with_device(selected_device['host'])
                    break
                else:
                    print(f"Invalid selection. Please enter a number between 1 and {len(devices)}.")
            except ValueError:
                print("Please enter a valid number.")
    
    if credentials:
        save_credentials_to_file(credentials, args.output)
        
        # Print example usage
        print("\nExample usage in Python code:")
        print(f"""
from asyncmiele import MieleClient

# Option 1: Load credentials from file
import json
with open("{args.output}", "r") as f:
    creds = json.load(f)
    
client = MieleClient.from_hex(
    creds["host"],
    creds["group_id"],
    creds["group_key"]
)

# Option 2: Use credentials directly
client = MieleClient.from_hex(
    "{credentials['host']}",
    "{credentials['group_id']}",
    "{credentials['group_key']}"
)
""")
    else:
        print("\nFailed to obtain device credentials.")
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Obtain Miele device credentials and save them to a JSON file"
    )
    parser.add_argument("--host", help="Device IP address or hostname (optional)")
    parser.add_argument(
        "--output", required=True, help="Path to save the credentials JSON file"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args)) 