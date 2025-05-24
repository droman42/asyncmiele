#!/usr/bin/env python3
"""
Discover Miele devices in setup mode and display their temporary SSIDs.

This script scans the local network for Miele devices that are in setup mode
and displays the temporary SSID information needed for WiFi configuration.
This is Step 1 of the 3-step configuration process.
"""

import argparse
import asyncio
import json
import sys
from typing import Dict, Any

from asyncmiele.utils.provisioning import scan_for_miele_devices, detect_device_id, detect_setup_mode_ssid


def _make_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Discover Miele devices in setup mode"
    )
    p.add_argument("--subnet", default=None,
                   help="Subnet to scan in CIDR notation (default: auto-detect)")
    p.add_argument("--timeout", type=float, default=2.0,
                   help="Timeout for connection attempts (default: 2.0)")
    p.add_argument("--format", choices=["console", "json"], default="console",
                   help="Output format (default: console)")
    p.add_argument("--scan-wifi", action="store_true",
                   help="Also scan for Miele WiFi access points")
    return p


async def discover_setup_devices(args: argparse.Namespace) -> None:
    """Discover devices in setup mode and display temporary SSIDs."""
    
    print("Scanning for Miele devices in setup mode...", file=sys.stderr)
    
    # Focus on setup mode detection
    devices = await scan_for_miele_devices(
        subnet=args.subnet,
        timeout=args.timeout
    )
    
    # Filter for setup mode devices and enhance with device IDs
    setup_devices = {}
    for ip, device_info in devices.items():
        # Try to detect device ID for each discovered device
        device_id = await detect_device_id(ip, timeout=args.timeout)
        if device_id:
            device_info['device_id'] = device_id
        
        # Include all devices but mark setup mode status
        setup_devices[ip] = device_info
    
    # Enhanced temporary SSID detection
    wifi_ssids = []
    if args.scan_wifi:
        print("Scanning for Miele WiFi access points...", file=sys.stderr)
        wifi_ssids = detect_setup_mode_ssid()
    
    # Enhanced console output
    if args.format == "console":
        print("=== Miele Device Setup Discovery ===\n")
        if not setup_devices:
            print("❌ No devices found in setup mode.")
            print("\nTroubleshooting:")
            print("1. Ensure device is in setup mode (usually by holding a button)")
            print("2. Check if device is broadcasting a WiFi access point")
            print("3. Verify you're on the same network segment")
        else:
            for ip, device_info in setup_devices.items():
                print(f"✅ Device found at {ip}")
                print(f"   📋 Device ID: {device_info.get('device_id', 'Unknown')}")
                print(f"   🏷️  Device Type: {device_info.get('device_type', 'Unknown')}")
                print(f"   🔧 Setup Mode: {device_info.get('setup_mode', 'Unknown')}")
                if 'temp_ssid' in device_info:
                    print(f"   🔑 Temporary SSID: {device_info['temp_ssid']}")
                print()
        
        if wifi_ssids:
            print("🔍 Discovered Miele WiFi Access Points:")
            for ssid in wifi_ssids:
                print(f"   📶 {ssid}")
            print()
            
        if setup_devices:
            print("Next Steps:")
            print("1. Note the Device ID from above (you'll need it for Step 3)")
            print("2. Run WiFi configuration:")
            print("   python scripts/configure_device_wifi.py --ap-ssid <TEMP_SSID> --ssid <YOUR_WIFI> --password <PASSWORD>")
            print("3. After WiFi is configured, run profile creation:")
            print("   python scripts/create_device_profile.py --host <DEVICE_IP> --device-id <DEVICE_ID> --output config.json")
    
    elif args.format == "json":
        # JSON output for scripting
        output = {
            "devices": [
                {
                    "ip": ip,
                    "device_id": device_info.get("device_id"),
                    "device_type": device_info.get("device_type"),
                    "temp_ssid": device_info.get("temp_ssid"),
                    "setup_mode": device_info.get("setup_mode", False)
                }
                for ip, device_info in setup_devices.items()
            ],
            "wifi_access_points": wifi_ssids if args.scan_wifi else []
        }
        print(json.dumps(output, indent=2))


async def _async_main(args: argparse.Namespace) -> None:
    try:
        await discover_setup_devices(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = _make_argparser()
    args = parser.parse_args()
    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        print("Aborted by user", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main() 