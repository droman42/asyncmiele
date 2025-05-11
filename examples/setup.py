"""
Example script for registering a new Miele device.

This script shows how to register with a Miele device in commissioning mode
and obtain the credentials needed for API access.

Usage:
    python setup.py --host 192.168.1.123
"""

import asyncio
import argparse
import sys

from asyncmiele import easy_setup
from asyncmiele.exceptions import MieleException


async def register_device(host: str) -> None:
    """
    Register with a Miele device and print the credentials.
    
    Args:
        host: Device hostname or IP address
    """
    try:
        print(f"Attempting to register with Miele device at {host}...")
        print("Make sure the device is in commissioning/registration mode.")
        print("This typically means it's connected to WiFi but not yet set up in the Miele app.")
        
        device_id, group_id, group_key = await easy_setup(host)
        
        print("\nRegistration successful!")
        print(f"\nDevice ID: {device_id}")
        print(f"Group ID: {group_id}")
        print(f"Group Key: {group_key}")
        
        print("\nStore these credentials securely. You'll need them to connect to the device.")
        print("\nExample configuration:")
        print(f"""
# For the discovery example
python examples/discover.py --host {host} --group-id {group_id} --group-key {group_key}

# For direct use in code:
from asyncmiele import MieleClient

client = MieleClient(
    host="{host}",
    group_id=bytes.fromhex("{group_id}"),
    group_key=bytes.fromhex("{group_key}")
)
""")
        
    except MieleException as e:
        print(f"Error: {e}")
        print("\nRegistration failed. Make sure the device is in commissioning mode and is reachable.")
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Register with a Miele device")
    parser.add_argument("--host", required=True, help="Device IP address or hostname")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(register_device(args.host)) 