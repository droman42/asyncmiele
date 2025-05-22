#!/usr/bin/env python3
"""
Example script demonstrating connection optimization features.

This script shows how to use the ConnectionManager to manage connections
to multiple Miele devices with optimized performance and reliability.
"""

import asyncio
import argparse
import logging
import sys
from typing import List, Dict, Any
import json
from pathlib import Path

from asyncmiele import (
    ConnectionManager, DeviceProfile, MieleCredentials, 
    MieleDeviceConfig, ConnectionState
)
from asyncmiele.connection.health import ConnectionHealthMonitor
from asyncmiele.models.device_profile import DeviceProfile


async def device_monitoring_example(
    profiles: List[DeviceProfile], 
    check_interval: float = 15.0
) -> None:
    """Example of monitoring multiple devices with optimized connections.
    
    Args:
        profiles: List of device profiles to monitor
        check_interval: Interval between device state checks
    """
    # Create connection manager
    connection_manager = ConnectionManager(
        max_connections=len(profiles) + 2,  # Allow for a few extra connections
        health_check_interval=30.0
    )
    
    # Register health state change callback
    async def on_health_state_change(device_id: str, state: ConnectionState) -> None:
        print(f"Device {device_id} connection state changed to: {state.value}")
        
        # Take action based on state
        if state == ConnectionState.UNHEALTHY:
            print(f"Attempting to recover connection to {device_id}...")
            
    # Start manager
    async with connection_manager:
        # Initialize clients for all devices
        clients = {}
        for profile in profiles:
            try:
                # Get client from manager
                client = await connection_manager.get_client(profile.device_id, profile)
                clients[profile.device_id] = client
                
                # Register health state callback for this device
                health_monitor = connection_manager.get_health_monitor()
                health_monitor.register_state_callback(profile.device_id, on_health_state_change)
                
                print(f"Connected to device: {profile.device_id}")
            except Exception as e:
                print(f"Failed to connect to device {profile.device_id}: {e}")
        
        # Main monitoring loop
        try:
            while True:
                # Get state of all devices
                for device_id, client in list(clients.items()):
                    try:
                        # Wrap operation in execute_with_retry
                        state = await connection_manager.execute_with_retry(
                            device_id,
                            lambda: client.get_device_state(device_id)
                        )
                        
                        # Display state information
                        status = getattr(state, "status", "unknown")
                        print(f"Device {device_id}: {status}")
                        
                    except Exception as e:
                        print(f"Error getting state for {device_id}: {e}")
                        
                # Sleep between checks
                await asyncio.sleep(check_interval)
                
        except KeyboardInterrupt:
            print("Monitoring stopped by user")
        except Exception as e:
            print(f"Error in monitoring loop: {e}")
            
        # Unregister callbacks
        health_monitor = connection_manager.get_health_monitor()
        for profile in profiles:
            health_monitor.unregister_state_callback(profile.device_id, on_health_state_change)


async def device_reset_example(profile: DeviceProfile) -> None:
    """Example of handling device resets.
    
    Args:
        profile: Device profile
    """
    from asyncmiele import DeviceResetter
    
    # Create connection manager
    connection_manager = ConnectionManager()
    
    # Create device resetter
    resetter = DeviceResetter()
    
    # Start manager
    async with connection_manager:
        try:
            # Get client from manager
            client = await connection_manager.get_client(profile.device_id, profile)
            
            # Check if device has been reset
            is_reset = await resetter.detect_factory_reset(client, profile.device_id)
            
            if is_reset:
                print(f"Device {profile.device_id} appears to be in reset mode")
                
                # Attempt recovery
                success, new_client = await resetter.recover_from_reset(
                    profile.device_id, profile
                )
                
                if success:
                    print(f"Successfully recovered device {profile.device_id}")
                else:
                    print(f"Failed to recover device {profile.device_id}")
            else:
                print(f"Device {profile.device_id} is not in reset mode")
                
                # Optional: Initiate a reset (uncomment to test)
                # print(f"Initiating reset for device {profile.device_id}...")
                # success = await resetter.initiate_reset(client, profile.device_id)
                # print(f"Reset initiated: {success}")
                
        except Exception as e:
            print(f"Error in reset example: {e}")


def load_profiles(config_file: str) -> List[DeviceProfile]:
    """Load device profiles from a configuration file.
    
    Args:
        config_file: Path to configuration file
        
    Returns:
        List of device profiles
    """
    profiles = []
    
    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
            
        for device_config in config_data.get('devices', []):
            # Create device configuration
            config = MieleDeviceConfig(
                host=device_config['host']
            )
            
            # Create credentials
            credentials = MieleCredentials(
                group_id=bytes.fromhex(device_config['group_id']),
                group_key=bytes.fromhex(device_config['group_key'])
            )
            
            # Create profile
            profile = DeviceProfile(
                device_id=device_config['id'],
                config=config,
                credentials=credentials
            )
            
            profiles.append(profile)
            
    except Exception as e:
        print(f"Error loading configuration: {e}")
        
    return profiles


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Example of connection optimization with Miele devices"
    )
    parser.add_argument(
        "--config", required=True,
        help="Path to configuration file with device profiles"
    )
    parser.add_argument(
        "--example", choices=["monitor", "reset"], default="monitor",
        help="Example to run (monitor or reset)"
    )
    parser.add_argument(
        "--device-id", 
        help="Device ID for reset example (required for reset example)"
    )
    parser.add_argument(
        "--interval", type=float, default=15.0,
        help="Check interval for monitoring example (seconds)"
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
    
    # Load profiles
    profiles = load_profiles(args.config)
    
    if not profiles:
        print("No device profiles found in configuration file")
        return 1
        
    print(f"Loaded {len(profiles)} device profiles")
    
    # Run appropriate example
    if args.example == "monitor":
        asyncio.run(device_monitoring_example(profiles, args.interval))
    elif args.example == "reset":
        if not args.device_id:
            print("Device ID is required for reset example")
            return 1
            
        # Find profile for device
        profile = next((p for p in profiles if p.device_id == args.device_id), None)
        if not profile:
            print(f"No profile found for device {args.device_id}")
            return 1
            
        asyncio.run(device_reset_example(profile))
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 