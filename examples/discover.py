"""
Example script for discovering and reading state from Miele devices.

Usage:
    python discover.py --host 192.168.1.123 --group-id <GROUP_ID> --group-key <GROUP_KEY>
"""

import asyncio
import argparse
import sys
from typing import Optional

from asyncmiele import MieleClient
from asyncmiele.exceptions import MieleException


async def discover_devices(
    host: str,
    group_id: str,
    group_key: str
) -> None:
    """
    Discover and print information about Miele devices.
    
    Args:
        host: Device hostname or IP address
        group_id: Group ID as hex string
        group_key: Group key as hex string
    """
    try:
        # Create client
        client = MieleClient(
            host=host,
            group_id=bytes.fromhex(group_id),
            group_key=bytes.fromhex(group_key)
        )
        
        # Get devices
        print(f"Discovering Miele devices at {host}...")
        devices = await client.get_devices()
        
        if not devices:
            print("No devices found.")
            return
            
        print(f"Found {len(devices)} device(s):")
        
        # Print device information
        for device_id, device in devices.items():
            print("\n" + "=" * 50)
            print(f"Device ID: {device_id}")
            print(f"Name: {device.name}")
            print(f"Type: {device.ident.device_type}")
            print(f"Serial: {device.ident.fab_number}")
            
            print("\nState:")
            print(f"  Status: {device.state.status}")
            
            if device.state.program_type:
                print(f"  Program: {device.state.program_type}")
                
            if device.state.program_phase:
                print(f"  Phase: {device.state.program_phase}")
                
            if device.state.remaining_time:
                minutes = device.state.remaining_time // 60
                seconds = device.state.remaining_time % 60
                print(f"  Remaining time: {minutes:02d}:{seconds:02d}")
                
            # Print raw state for debugging
            print("\nRaw state data:")
            for key, value in device.state.raw_state.items():
                if isinstance(value, dict) and "value_raw" in value and "value_localized" in value:
                    print(f"  {key}: {value['value_localized']} (raw: {value['value_raw']})")
                else:
                    print(f"  {key}: {value}")
                    
    except MieleException as e:
        print(f"Error: {e}")
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Discover Miele devices")
    
    parser.add_argument("--host", required=True, help="Device IP address or hostname")
    parser.add_argument("--group-id", required=True, help="Group ID in hex format")
    parser.add_argument("--group-key", required=True, help="Group key in hex format")
    
    return parser.parse_args()
    

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(discover_devices(args.host, args.group_id, args.group_key)) 