#!/usr/bin/env python3
"""
Factory Reset Script for Miele Devices.

This script provides functionality to perform a factory reset on a Miele device
and optionally help with recovery after the reset.
"""

import asyncio
import argparse
import logging
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from asyncmiele import (
    ConnectionManager, DeviceProfile, MieleCredentials, 
    DeviceResetter, MieleClient
)
from asyncmiele.exceptions.connection import DeviceResetError, ConnectionLostError
from asyncmiele.utils.discovery import discover_devices


async def factory_reset_device(
    profile: DeviceProfile,
    wait_for_recovery: bool = True,
    recovery_timeout: float = 120.0,
    confirm: bool = True
) -> bool:
    """Perform a factory reset on a device.
    
    Args:
        profile: Device profile with connection information
        wait_for_recovery: Whether to wait for the device to be discoverable after reset
        recovery_timeout: How long to wait for the device to become discoverable
        confirm: Whether to ask for user confirmation before proceeding
        
    Returns:
        True if reset was successful
    """
    device_id = profile.device_id
    host = profile.host
    
    # User confirmation
    if confirm:
        print(f"\n⚠️  WARNING: You are about to factory reset device {device_id} at {host} ⚠️")
        print("This will erase all configuration and return the device to factory settings.")
        print("The device will need to be reconfigured after the reset.")
        confirmation = input("Are you sure you want to proceed? (y/N): ")
        if confirmation.lower() not in ["y", "yes"]:
            print("Reset canceled.")
            return False
    
    # Create connection manager
    connection_manager = ConnectionManager(retry_count=2, retry_delay=1.0)
    
    # Create device resetter with custom timeout
    resetter = DeviceResetter(
        discovery_timeout=10.0,
        recovery_timeout=recovery_timeout,
        max_retries=3
    )
    
    # Track device MAC address before reset if possible
    mac_address = None
    
    # Start connection manager
    async with connection_manager:
        try:
            print(f"Connecting to device {device_id} at {host}...")
            
            # Get client from manager
            client = await connection_manager.get_client(device_id, profile)
            
            # Try to get device info to cache MAC
            try:
                from asyncmiele.utils.discovery import get_device_info
                device_info = await get_device_info(host)
                if device_info and "mac" in device_info:
                    mac_address = device_info["mac"]
                    resetter.register_device_mac(device_id, mac_address)
                    print(f"Identified device MAC address: {mac_address}")
            except Exception as e:
                print(f"Could not determine device MAC address: {e}")
                
            # Perform the reset
            print(f"Initiating factory reset for device {device_id}...")
            reset_initiated = await resetter.initiate_reset(client, device_id)
            
            if not reset_initiated:
                print("❌ Factory reset failed to initiate. Device may not support remote reset.")
                return False
                
            print("✅ Factory reset initiated successfully.")
            
            # Wait for device to enter reset/setup mode if requested
            if wait_for_recovery:
                print(f"Waiting for device to enter setup mode (timeout: {recovery_timeout}s)...")
                setup_mode = await resetter._wait_for_reset_mode(device_id)
                
                if setup_mode:
                    print("✅ Device has entered setup mode and is ready for reconfiguration.")
                    
                    # Show discovery information
                    print("\nDiscovering devices in setup mode...")
                    devices = await discover_devices(timeout=10.0)
                    setup_devices = [d for d in devices if d.get("setup_mode", False)]
                    
                    if setup_devices:
                        print(f"\nFound {len(setup_devices)} device(s) in setup mode:")
                        for idx, dev in enumerate(setup_devices, 1):
                            print(f"  {idx}. IP: {dev.get('host', 'Unknown')}, MAC: {dev.get('mac', 'Unknown')}")
                            
                        print("\nTo reconfigure the device, use the MieleSetupClient:")
                        print("  python -m asyncmiele.scripts.configure_device_wifi --help")
                    else:
                        print("No devices in setup mode found. The device might not be broadcasting.")
                else:
                    print("⚠️ Device did not enter setup mode within the timeout period.")
                    print("It may still be resetting or might require manual intervention.")
                    
            return reset_initiated
                
        except DeviceResetError as e:
            print(f"❌ Error during reset operation: {e}")
            return False
        except ConnectionLostError as e:
            print(f"❌ Connection lost: {e}")
            print("This is expected during a reset as the device disconnects.")
            return True  # Connection loss during reset is actually expected
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False


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


async def discover_and_list() -> None:
    """Discover and list all Miele devices on the network."""
    print("Discovering Miele devices on the network...")
    devices = await discover_devices(timeout=10.0)
    
    if not devices:
        print("No Miele devices found.")
        return
        
    print(f"\nFound {len(devices)} device(s):")
    for idx, device in enumerate(devices, 1):
        setup_mode = "✓" if device.get("setup_mode", False) else "✗"
        print(f"  {idx}. ID: {device.get('id', 'Unknown')}")
        print(f"     IP: {device.get('host', 'Unknown')}")
        print(f"     MAC: {device.get('mac', 'Unknown')}")
        print(f"     Setup Mode: {setup_mode}")
        print(f"     Model: {device.get('type', 'Unknown')}")
        print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Factory Reset Tool for Miele Devices"
    )
    parser.add_argument(
        "--config", type=str,
        help="Path to configuration file with device profiles"
    )
    parser.add_argument(
        "--device-id", type=str,
        help="Device ID to reset"
    )
    parser.add_argument(
        "--host", type=str,
        help="Device IP address or hostname (alternative to config file)"
    )
    parser.add_argument(
        "--group-id", type=str,
        help="Group ID in hex (required if using --host)"
    )
    parser.add_argument(
        "--group-key", type=str,
        help="Group Key in hex (required if using --host)"
    )
    parser.add_argument(
        "--no-wait", action="store_true",
        help="Don't wait for the device to enter setup mode after reset"
    )
    parser.add_argument(
        "--timeout", type=float, default=120.0,
        help="Timeout in seconds to wait for device to enter setup mode"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Skip confirmation prompt"
    )
    parser.add_argument(
        "--discover", action="store_true",
        help="Discover and list Miele devices on the network"
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
    
    # Just discover devices if requested
    if args.discover:
        asyncio.run(discover_and_list())
        return 0
    
    # Load profile from config or command line args
    profile = None
    
    if args.config:
        profile = load_profile(args.config, args.device_id)
    elif args.host and args.group_id and args.group_key:
        try:
            # Create profile from command line args
            credentials = MieleCredentials(
                group_id=bytes.fromhex(args.group_id),
                group_key=bytes.fromhex(args.group_key)
            )
            # Use host as device_id if not provided
            device_id = args.device_id or args.host.replace(".", "_")
            profile = DeviceProfile(
                device_id=device_id,
                host=args.host,
                credentials=credentials
            )
        except Exception as e:
            print(f"Error creating device profile: {e}")
    
    if not profile:
        print("Error: Must provide either a config file or host, group-id, and group-key.")
        parser.print_help()
        return 1
    
    # Perform the reset
    success = asyncio.run(factory_reset_device(
        profile,
        wait_for_recovery=not args.no_wait,
        recovery_timeout=args.timeout,
        confirm=not args.force
    ))
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main()) 