"""
Example script for discovering Miele devices on the local network.

This script uses UPnP/SSDP to find Miele devices on your network.

Usage:
    python discover_network.py
"""

import asyncio
import sys

from asyncmiele.utils.discovery import discover_devices
from asyncmiele.exceptions import MieleException


async def discover_miele_devices() -> None:
    """Discover and print information about Miele devices on the network."""
    try:
        print("Searching for Miele devices on the local network...")
        print("This may take a few seconds...")
        
        devices = await discover_devices(timeout=5.0)
        
        if not devices:
            print("\nNo Miele devices found.")
            print("Make sure your devices are connected to the network and try again.")
            return
            
        print(f"\nFound {len(devices)} Miele device(s):")
        
        for idx, device in enumerate(devices, 1):
            print(f"\nDevice {idx}:")
            print(f"  IP Address: {device['host']}")
            
            if 'server' in device:
                print(f"  Server: {device['server']}")
                
            if 'location' in device:
                print(f"  Device URL: {device['location']}")
                
            print("\nTo set up this device:")
            print(f"  python examples/setup.py --host {device['host']}")
            
    except MieleException as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(discover_miele_devices()) 