#!/usr/bin/env python3
"""
Diagnostic tool for exploring Miele device capabilities.

This script attempts to connect to a Miele device and investigate
what API endpoints and DOP2 leafs it supports.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

from asyncmiele.api.client import MieleClient
from asyncmiele.capabilities import DeviceCapability


async def check_device_info(client: MieleClient, device_id: str) -> Dict[str, Any]:
    """Check basic device information endpoints."""
    results = {}
    
    # Try getting device list
    print("Checking available devices...")
    try:
        devices = await client.get_devices()
        results["devices"] = list(devices.keys())
        if device_id not in devices:
            print(f"WARNING: Device {device_id} not found in device list!")
        print(f"Found {len(devices)} devices: {', '.join(devices.keys())}")
    except Exception as e:
        print(f"ERROR getting device list: {e}")
        results["devices_error"] = str(e)
    
    # Check if this specific device exists
    print(f"\nChecking device {device_id}...")
    try:
        device = await client.get_device(device_id)
        results["device_exists"] = True
        print(f"Device {device_id} exists")
    except Exception as e:
        print(f"ERROR getting device {device_id}: {e}")
        results["device_error"] = str(e)
    
    # Try device identification
    print("\nChecking device identification...")
    try:
        ident = await client.get_device_ident(device_id)
        results["ident"] = ident.model_dump() if hasattr(ident, "model_dump") else str(ident)
        print(f"Device identification successful: {ident.device_type or ident.tech_type}")
    except Exception as e:
        print(f"ERROR getting device identification: {e}")
        results["ident_error"] = str(e)
    
    # Try device state
    print("\nChecking device state...")
    try:
        state = await client.get_device_state(device_id)
        results["state"] = state.model_dump() if hasattr(state, "model_dump") else str(state)
        print(f"Device state successful: Status={getattr(state, 'status', 'unknown')}")
    except Exception as e:
        print(f"ERROR getting device state: {e}")
        results["state_error"] = str(e)
    
    return results


async def check_wake_up(client: MieleClient, device_id: str) -> Dict[str, Any]:
    """Test wake-up functionality."""
    results = {}
    
    print("\nAttempting to wake up device...")
    try:
        await client.wake_up(device_id)
        results["wake_up"] = "success"
        print("Wake up command successful")
    except Exception as e:
        print(f"ERROR waking up device: {e}")
        results["wake_up_error"] = str(e)
    
    return results


async def test_dop2_leafs(client: MieleClient, device_id: str, specific_leafs=None, timeout=10.0) -> Dict[str, Any]:
    """Test various DOP2 leaf combinations to see which are supported."""
    results = {}
    
    # Common leaf pairs to test
    if specific_leafs:
        test_leafs = specific_leafs
    else:
        test_leafs = [
            # Program catalog related
            (2, 1584),  # New program list
            (14, 1570),  # Old program list
            (14, 2570),  # String table
            # Device state related
            (2, 256),   # Device state
            (2, 144),   # Device ident
            # Settings related
            (2, 105),   # Settings
            (2, 114),   # Settings list
        ]
    
    print("\nTesting DOP2 leaf access...")
    leaf_results = {}
    
    for unit, attribute in test_leafs:
        try:
            print(f"Testing leaf {unit}/{attribute}...")
            # Create a task with a timeout
            task = asyncio.create_task(client.read_dop2_leaf(device_id, unit, attribute))
            
            try:
                # Wait for the task with a timeout
                data = await asyncio.wait_for(task, timeout)
                leaf_results[f"{unit}/{attribute}"] = {
                    "success": True,
                    "size": len(data),
                    "data_preview": data[:20].hex() if data else "empty"
                }
                print(f"  Success! Received {len(data)} bytes")
            except asyncio.TimeoutError:
                print(f"  ERROR: Timeout after {timeout} seconds")
                leaf_results[f"{unit}/{attribute}"] = {
                    "success": False,
                    "error": f"Timeout after {timeout} seconds"
                }
            
        except Exception as e:
            print(f"  ERROR: {e}")
            leaf_results[f"{unit}/{attribute}"] = {
                "success": False,
                "error": str(e)
            }
            
        # Add a delay between requests to avoid overwhelming the device
        await asyncio.sleep(2)
    
    results["leaf_tests"] = leaf_results
    return results


async def run_diagnosis(client, device_id, args):
    """Run diagnostics for a device."""
    results = {}
    
    # Check if device exists
    try:
        device = await client.get_device(device_id)
        results["device_exists"] = True
        results["device_info"] = {
            "name": device.ident.device_name,
            "type": device.ident.device_type,
        }
    except Exception as e:
        results["device_exists"] = False
        results["device_error"] = str(e)
        return results
    
    # Check device state
    try:
        state = await client.get_device_state(device_id)
        results["state"] = state.model_dump()
    except Exception as e:
        results["state"] = None
        results["state_error"] = str(e)
    
    # Detect capabilities first
    try:
        capabilities = await client.detect_capabilities(device_id)
        results["capabilities"] = {cap.name: cap in capabilities for cap in DeviceCapability if cap != DeviceCapability.NONE}
        print(f"Detected capabilities: {[cap.name for cap in DeviceCapability if cap in capabilities and cap != DeviceCapability.NONE]}")
    except Exception as e:
        results["capabilities_error"] = str(e)
        capabilities = DeviceCapability.NONE
    
    # Try to wake up device if requested and supported
    if not args.no_wake:
        if DeviceCapability.WAKE_UP in capabilities:
            try:
                print("\nAttempting to wake up device (capability detected)...")
                await client.wake_up(device_id)
                results["wake_up"] = "success"
                print("Wake up command successful")
                
                # Wait a bit for the device to wake up
                await asyncio.sleep(args.delay)
            except Exception as e:
                print(f"ERROR waking up device: {e}")
                results["wake_up"] = "error"
                results["wake_up_error"] = str(e)
        else:
            print("\nSkipping wake-up: Device does not support WAKE_UP capability")
            results["wake_up"] = "skipped_unsupported"
    
    # Test DOP2 leaves
    if args.brief:
        # Test only specified leaves for brief mode
        specific_leafs = [
            (2, 1584),  # Program catalog (new method)
            (14, 1570)  # Program catalog (fallback method)
        ]
        dop2_results = await test_dop2_leafs(
            client, device_id, 
            specific_leafs=specific_leafs,
            timeout=args.timeout
        )
    else:
        # Test all common leaves
        dop2_results = await test_dop2_leafs(
            client, device_id,
            timeout=args.timeout
        )
    
    results["dop2_leaves"] = dop2_results
    
    return results


async def main():
    parser = argparse.ArgumentParser(description="Diagnostic tool for exploring Miele device capabilities")
    parser.add_argument("--host", required=True, help="IP or hostname of the appliance")
    parser.add_argument("--device-id", required=True, help="Device identifier (12 digits)")
    parser.add_argument("--group-id", required=True, metavar="HEX32",
                        help="GroupID in hex (32 characters / 16 bytes)")
    parser.add_argument("--group-key", required=True, metavar="HEX32",
                        help="GroupKey in hex (32 characters / 16 bytes)")
    parser.add_argument("--out", default="device_diagnosis.json", 
                        help="Output JSON file (default: device_diagnosis.json)")
    parser.add_argument("--no-wake", action="store_true", help="Skip wake-up attempt")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between API requests in seconds")
    parser.add_argument("--brief", action="store_true", help="Only test critical leaf nodes")
    parser.add_argument("--timeout", type=float, default=10.0, help="Timeout for DOP2 leaf requests in seconds")
    args = parser.parse_args()
    
    # Create client
    client = MieleClient(
        host=args.host,
        group_id=bytes.fromhex(args.group_id),
        group_key=bytes.fromhex(args.group_key),
    )
    
    try:
        # Run diagnostics
        print(f"Starting diagnostics for {args.device_id} at {args.host}")
        results = await run_diagnosis(client, args.device_id, args)
        
        # Save results to file
        with open(args.out, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nDiagnostic results saved to {args.out}")
        
    except Exception as e:
        print(f"ERROR during diagnostics: {e}")
        
    finally:
        # Close the client
        await client.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDiagnostics aborted by user")
        sys.exit(1) 