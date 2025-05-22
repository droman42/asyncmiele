#!/usr/bin/env python3
"""
Test script for device capability detection.

This script demonstrates how to use the device capability detection system
to adapt behavior based on a device's capabilities.
"""

import argparse
import asyncio
import json
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from asyncmiele.api.client import MieleClient
from asyncmiele.capabilities import DeviceCapability
from asyncmiele.models.device_profile import DeviceProfile
from asyncmiele.models.credentials import MieleCredentials
from asyncmiele.models.device_config import MieleDeviceConfig
from asyncmiele.exceptions.config import UnsupportedCapabilityError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def _make_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Test device capability detection"
    )
    p.add_argument("--host", required=True, help="IP or hostname of the appliance")
    p.add_argument("--device-id", required=True, help="Device identifier (12 digits)")
    p.add_argument("--group-id", required=True, metavar="HEX32",
                   help="GroupID in hex (32 characters / 16 bytes)")
    p.add_argument("--group-key", required=True, metavar="HEX32",
                   help="GroupKey in hex (32 characters / 16 bytes)")
    p.add_argument("--output", "-o", help="Output file for saving the device profile")
    p.add_argument("--save-profile", action="store_true", help="Save the device profile to a file")
    p.add_argument("--timeout", type=float, default=5.0, help="Request timeout in seconds")
    return p


async def test_capabilities(args: argparse.Namespace) -> None:
    """Test capability detection for a device."""
    # Create client
    client = MieleClient(
        host=args.host,
        group_id=bytes.fromhex(args.group_id),
        group_key=bytes.fromhex(args.group_key),
        timeout=args.timeout
    )
    
    try:
        async with client:
            logger.info(f"Testing capabilities for device {args.device_id}")
            
            # Get device information
            device = await client.get_device(args.device_id)
            logger.info(f"Device: {device.ident.device_name} ({device.ident.device_type})")
            
            # Create credentials and device config objects
            credentials = MieleCredentials(
                group_id=args.group_id,
                group_key=args.group_key
            )
            
            config = MieleDeviceConfig(
                host=args.host
            )
            
            # Create device profile
            profile = DeviceProfile(
                device_id=args.device_id,
                device_type=device.ident.type,
                friendly_name=device.ident.device_name,
                config=config,
                credentials=credentials,
                timeout=args.timeout
            )
            
            # Detect capabilities
            capabilities = await client.detect_capabilities(args.device_id)
            
            # Show detected capabilities
            logger.info("Detected capabilities:")
            for capability in DeviceCapability:
                if capability != DeviceCapability.NONE and capability in capabilities:
                    logger.info(f"  ✓ {capability.name}")
                elif capability != DeviceCapability.NONE:
                    logger.info(f"  ✗ {capability.name}")
            
            # Test a capability-aware operation
            logger.info("\nTesting wake-up capability:")
            try:
                await client.wake_up(args.device_id)
                logger.info("  ✓ Wake-up successful")
            except UnsupportedCapabilityError:
                logger.info("  ✗ Device does not support wake-up")
            except Exception as e:
                logger.info(f"  ✗ Wake-up failed: {str(e)}")
            
            logger.info("\nTesting remote start capability:")
            try:
                can_remote = await client.can_remote_start(args.device_id)
                logger.info(f"  ✓ Remote start supported: {can_remote}")
            except UnsupportedCapabilityError:
                logger.info("  ✗ Device does not support remote start")
            except Exception as e:
                logger.info(f"  ✗ Remote start check failed: {str(e)}")
            
            logger.info("\nTesting program catalog capability:")
            try:
                catalog = await client.extract_program_catalog(args.device_id)
                program_count = len(catalog.get("programs", []))
                logger.info(f"  ✓ Program catalog supported: {program_count} programs")
            except UnsupportedCapabilityError:
                logger.info("  ✗ Device does not support program catalog")
            except Exception as e:
                logger.info(f"  ✗ Program catalog extraction failed: {str(e)}")
            
            # Save profile if requested
            if args.save_profile:
                output_path = args.output or f"device_profile_{args.device_id}.json"
                with open(output_path, "w") as f:
                    json.dump(profile.model_dump(), f, indent=2)
                logger.info(f"Device profile saved to {output_path}")
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)


async def _async_main(args: argparse.Namespace) -> None:
    await test_capabilities(args)


def main():
    parser = _make_argparser()
    args = parser.parse_args()
    
    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        logger.info("Aborted by user")
        sys.exit(2)


if __name__ == "__main__":
    main() 