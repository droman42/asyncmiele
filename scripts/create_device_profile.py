#!/usr/bin/env python3
"""
Create complete device profile configuration.

This script handles the final configuration steps after WiFi setup:
1. Generate and provision security credentials (can be skipped with --skip-provisioning)
2. Detect device capabilities
3. Extract program catalog
4. Create complete device profile JSON

This is Step 3 of the 3-step configuration process and replaces:
- generate_credentials.py
- provision_device_keys.py 
- test_capabilities.py
- dump_program_catalog.py

Use --skip-provisioning when the device is already provisioned with the specified credentials.
"""

import argparse
import asyncio
import json
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Set, Tuple

from asyncmiele.api.client import MieleClient
from asyncmiele.api.setup_client import MieleSetupClient
from asyncmiele.models.credentials import MieleCredentials
from asyncmiele.models.device_profile import DeviceProfile
from asyncmiele.models.device import MieleDevice
from asyncmiele.capabilities import DeviceCapability, detect_capabilities_as_sets
from asyncmiele.enums import DeviceTypeMiele
from asyncmiele.config.loader import save_device_profile, load_device_profile
from asyncmiele.validation.config import ConfigurationValidator, ValidationResult
from asyncmiele.exceptions.setup import ProvisioningError
from asyncmiele.exceptions.config import InvalidConfigurationError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def _make_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Create complete device profile configuration"
    )
    p.add_argument("--host", required=True, 
                   help="IP address of device (after WiFi configuration)")
    p.add_argument("--device-id", required=True,
                   help="Device ID (12 digits)")
    p.add_argument("--device-name", 
                   help="Friendly name for the device")
    p.add_argument("--output", "-o", required=True,
                   help="Output path for device profile JSON")
    p.add_argument("--credentials-file",
                   help="Use existing credentials file instead of generating new ones")
    p.add_argument("--skip-provisioning", action="store_true",
                   help="Skip credential provisioning (assume device is already provisioned)")
    p.add_argument("--skip-capabilities", action="store_true",
                   help="Skip capability detection (use defaults)")
    p.add_argument("--skip-catalog", action="store_true", 
                   help="Skip program catalog extraction")
    p.add_argument("--timeout", type=float, default=5.0,
                   help="Timeout for operations (default: 5.0)")
    p.add_argument("--skip-validation", action="store_true",
                   help="Skip final configuration validation")
    return p


def load_credentials_from_file(file_path: str) -> MieleCredentials:
    """Load credentials from a JSON file."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        if 'group_id' in data and 'group_key' in data:
            return MieleCredentials(
                group_id=data['group_id'],
                group_key=data['group_key']
            )
        else:
            raise ValueError("Credentials file does not contain required fields (group_id, group_key)")
    except (json.JSONDecodeError, IOError) as e:
        raise ValueError(f"Failed to load credentials from file: {str(e)}")


def convert_device_type_to_enum(device_type_str: str, friendly_name: str = None) -> DeviceTypeMiele:
    """Convert a device type string to DeviceTypeMiele enum."""
    # If device type string is empty or unknown, try to use friendly name
    if not device_type_str or device_type_str == "Unknown":
        if friendly_name:
            print(f"Device type detection failed, using friendly name: '{friendly_name}'")
            device_type_str = friendly_name
        else:
            return DeviceTypeMiele.NoUse
    
    # Try to match the device type string to an enum value
    device_type_lower = device_type_str.lower()
    
    # Common device type mappings
    type_mappings = {
        'oven': DeviceTypeMiele.Oven,
        'hob': DeviceTypeMiele.Cooktop,
        'cooktop': DeviceTypeMiele.Cooktop,
        'induction': DeviceTypeMiele.Cooktop,
        'dishwasher': DeviceTypeMiele.Dishwasher,
        'washing machine': DeviceTypeMiele.WashingMachine,
        'washer': DeviceTypeMiele.WashingMachine,
        'dryer': DeviceTypeMiele.TumbleDryer,
        'tumble dryer': DeviceTypeMiele.TumbleDryer,
        'microwave': DeviceTypeMiele.Microwave,
        'steam oven': DeviceTypeMiele.SteamOven,
        'coffee': DeviceTypeMiele.CoffeeMaker,
        'refrigerator': DeviceTypeMiele.Fridge,
        'freezer': DeviceTypeMiele.Freezer,
        'hood': DeviceTypeMiele.Hood,
    }
    
    # Check for direct matches
    for key, enum_val in type_mappings.items():
        if key in device_type_lower:
            print(f"Detected device type: {enum_val} (matched '{key}' in '{device_type_str}')")
            return enum_val
    
    # Try exact enum name match
    for enum_val in DeviceTypeMiele:
        if device_type_lower == enum_val.name.lower():
            print(f"Detected device type: {enum_val} (exact enum match)")
            return enum_val
    
    # Default fallback
    print(f"Could not determine device type from '{device_type_str}', defaulting to NoUse")
    return DeviceTypeMiele.NoUse


async def provision_credentials_to_device(host: str, credentials: MieleCredentials, timeout: float) -> bool:
    """Provision credentials to device (from provision_device_keys.py)."""
    client = MieleSetupClient(timeout=timeout)
    
    try:
        async with client:
            success = await client.provision_credentials(
                host=host,
                credentials=credentials,
                use_https=False,
                try_both_protocols=True,
                retry_count=2
            )
            return success
    except ProvisioningError as e:
        logger.error(f"Provisioning error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected provisioning error: {str(e)}")
        return False


async def get_device_information(host: str, device_id: str, credentials: MieleCredentials, timeout: float) -> MieleDevice:
    """Get basic device information."""
    client = MieleClient(
        host=host,
        group_id=credentials.get_id_bytes(),
        group_key=credentials.get_key_bytes(),
        timeout=timeout
    )
    
    async with client:
        device = await client.get_device(device_id)
        return device


async def extract_program_catalog(host: str, device_id: str, credentials: MieleCredentials, timeout: float) -> Tuple[Dict[str, Any], str]:
    """Extract program catalog (from dump_program_catalog.py)."""
    client = MieleClient(
        host=host,
        group_id=credentials.get_id_bytes(),
        group_key=credentials.get_key_bytes(),
        timeout=timeout
    )
    
    async with client:
        # Try to wake up device first
        try:
            await client.wake_up(device_id)
            await asyncio.sleep(1)
        except Exception:
            pass  # Continue even if wake fails
        
        # Extract catalog using client's method
        catalog = await client.get_program_catalog(device_id)
        extraction_method = catalog.get("extraction_method", "unknown")
        
        return catalog, extraction_method


async def validate_device_config(config_path: str) -> Optional[ValidationResult]:
    """Validate the created device configuration."""
    try:
        profile = load_device_profile(config_path)
        
        # Create client from profile for validation
        client = MieleClient.from_profile(profile)
        
        validator = ConfigurationValidator()
        result = await validator.validate_profile(profile, client)
        return result
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return None


async def create_device_profile(args: argparse.Namespace) -> None:
    """Create complete device profile through all configuration steps."""
    
    print("=== Miele Device Profile Creation ===\n")
    
    # Step 3a: Credential Management
    print("🔐 Step 1: Managing Credentials")
    if args.credentials_file:
        print(f"Loading credentials from: {args.credentials_file}")
        credentials = load_credentials_from_file(args.credentials_file)
    else:
        print("Generating new random credentials...")
        credentials = MieleCredentials.generate_random()
        print(f"Generated GroupID: {credentials.get_id_hex()}")
        print(f"Generated GroupKey: {credentials.get_key_hex()[:8]}...{credentials.get_key_hex()[-8:]}")
    
    # Step 3b: Provision Credentials
    if args.skip_provisioning:
        print("⏭️  Skipping credential provisioning (assuming device is already provisioned)")
        print("⚠️  Note: This assumes the device is already provisioned with the specified credentials")
    else:
        print(f"Provisioning credentials to device at {args.host}...")
        success = await provision_credentials_to_device(args.host, credentials, args.timeout)
        if not success:
            print("❌ Failed to provision credentials")
            sys.exit(1)
        print("✅ Credentials provisioned successfully")
    
    # Step 3c: Device Information
    print(f"\n🔍 Step 2: Gathering Device Information")
    try:
        device_info = await get_device_information(args.host, args.device_id, credentials, args.timeout)
        device_type_str = device_info.ident.type if hasattr(device_info.ident, 'type') else device_info.ident.device_type
        device_name = device_info.ident.device_name if hasattr(device_info.ident, 'device_name') else "Unknown Device"
        print(f"Device Type: {device_type_str}")
        print(f"Device Name: {device_name}")
    except Exception as e:
        print(f"⚠️  Could not get device information: {e}")
        device_type_str = "Unknown"
        device_name = "Unknown Device"
    
    # Convert device type string to enum
    # Use the user-provided friendly name as fallback for device type detection
    friendly_name_for_detection = args.device_name or device_name
    device_type = convert_device_type_to_enum(device_type_str, friendly_name_for_detection)
    
    # Step 3d: Capability Detection
    print(f"\n🧪 Step 3: Detecting Capabilities")
    if args.skip_capabilities:
        print("Skipping capability detection (using defaults)")
        capabilities = set()
        failed_capabilities = set()
    else:
        # Use library's built-in capability detection
        client = MieleClient(
            host=args.host,
            group_id=credentials.get_id_bytes(),
            group_key=credentials.get_key_bytes(),
            timeout=args.timeout
        )
        
        async with client:
            capabilities, failed_capabilities = await detect_capabilities_as_sets(
                client, args.device_id, device_type
            )
        
        print(f"Supported capabilities: {[cap.name for cap in capabilities]}")
        if failed_capabilities:
            print(f"Failed capabilities: {[cap.name for cap in failed_capabilities]}")
    
    # Step 3e: Program Catalog
    print(f"\n📋 Step 4: Extracting Program Catalog")
    if args.skip_catalog:
        print("Skipping program catalog extraction")
        program_catalog = None
        catalog_method = None
    else:
        try:
            program_catalog, catalog_method = await extract_program_catalog(
                args.host, args.device_id, credentials, args.timeout
            )
            program_count = len(program_catalog.get("programs", {}))
            print(f"✅ Extracted {program_count} programs using {catalog_method}")
        except Exception as e:
            print(f"⚠️  Program catalog extraction failed: {e}")
            program_catalog = None
            catalog_method = None
    
    # Step 3f: Create Device Profile
    print(f"\n📄 Step 5: Creating Device Profile")
    profile = DeviceProfile(
        device_id=args.device_id,
        device_type=device_type,
        friendly_name=args.device_name or device_name,
        host=args.host,                        # Direct field - no config wrapper
        timeout=args.timeout,                  # Direct field - no config wrapper
        credentials=credentials,
        capabilities=capabilities,
        failed_capabilities=failed_capabilities,
        capability_detection_date=datetime.now(),
        program_catalog=program_catalog,
        program_catalog_extraction_method=catalog_method
    )
    
    # Step 3g: Save Configuration
    print(f"💾 Step 6: Saving Configuration")
    save_device_profile(profile, args.output)
    print(f"✅ Device profile saved to: {args.output}")
    
    # Step 3h: Validation
    if not args.skip_validation:
        print(f"\n✅ Step 7: Validating Configuration")
        validation_result = await validate_device_config(args.output)
        if validation_result and validation_result.success:
            print("✅ Configuration validation successful!")
            print("\nDevice is ready for use!")
            print(f"Load in your service with: Appliance.from_config_file('{args.output}')")
        else:
            print("⚠️  Configuration validation found issues:")
            if validation_result:
                for issue in validation_result.issues:
                    print(f"  - {issue}")
                for issue in validation_result.capability_issues:
                    print(f"  - Capability: {issue}")
            else:
                print("  - Validation could not be completed")
    else:
        print("\n✅ Configuration creation complete!")
        print(f"Load in your service with: Appliance.from_config_file('{args.output}')")


async def _async_main(args: argparse.Namespace) -> None:
    await create_device_profile(args)


def main():
    parser = _make_argparser()
    args = parser.parse_args()
    
    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        logger.info("Aborted by user")
        sys.exit(2)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 