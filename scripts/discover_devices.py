#!/usr/bin/env python3
"""
Discover Miele devices on the local network.

This script scans the local network for Miele devices and reports details
about discovered devices.
"""

import argparse
import asyncio
import json
import sys
from typing import Dict, Any

from asyncmiele.utils.provisioning import scan_for_miele_devices, detect_device_id


def _make_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Discover Miele devices on the local network"
    )
    p.add_argument("--subnet", default=None,
                   help="Subnet to scan in CIDR notation (e.g., '192.168.1.0/24'). If not provided, all local subnets will be scanned.")
    p.add_argument("--timeout", type=float, default=2.0,
                   help="Timeout for connection attempts in seconds (default: 2.0)")
    p.add_argument("--format", choices=["json", "text"], default="text",
                   help="Output format (default: text)")
    p.add_argument("--out", default=None,
                   help="Output file path (default: stdout)")
    p.add_argument("--detect-ids", action="store_true",
                   help="Attempt to detect device IDs")
    return p


async def discover_and_output(args: argparse.Namespace) -> None:
    """Discover devices and output results in the specified format."""
    print("Scanning for Miele devices...", file=sys.stderr)
    
    # Scan for devices
    devices = await scan_for_miele_devices(
        subnet=args.subnet,
        timeout=args.timeout
    )
    
    # Detect device IDs if requested
    if args.detect_ids:
        print("Detecting device IDs...", file=sys.stderr)
        for ip, device_info in devices.items():
            device_id = await detect_device_id(ip, timeout=args.timeout)
            if device_id:
                device_info['device_id'] = device_id
    
    # Format the output
    if args.format == "json":
        output = json.dumps(devices, indent=2, ensure_ascii=False)
    else:  # text format
        if not devices:
            output = "No Miele devices found."
        else:
            lines = ["Discovered Miele devices:", ""]
            for ip, device_info in devices.items():
                lines.append(f"Device at {ip}:")
                lines.append(f"  Setup mode: {device_info.get('setup_mode', False)}")
                if 'device_id' in device_info:
                    lines.append(f"  Device ID: {device_info['device_id']}")
                if 'device_type' in device_info and device_info['device_type']:
                    lines.append(f"  Device type: {device_info['device_type']}")
                lines.append("")
            output = "\n".join(lines)
    
    # Write to file or stdout
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Results written to {args.out}", file=sys.stderr)
    else:
        print(output)


async def _async_main(args: argparse.Namespace) -> None:
    try:
        await discover_and_output(args)
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