#!/usr/bin/env python3
"""
Provision security credentials to a Miele device.

This script provides a command-line interface for provisioning security credentials
to a Miele device after it has been connected to your WiFi network.
"""

import argparse
import asyncio
import json
import sys
import logging
from typing import Dict, Any, Optional

from asyncmiele.api.setup_client import MieleSetupClient
from asyncmiele.models.credentials import MieleCredentials
from asyncmiele.exceptions.setup import ProvisioningError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def _make_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Provision security credentials to a Miele device"
    )
    p.add_argument("--host", required=True,
                   help="IP address or hostname of the device (after WiFi setup)")
    p.add_argument("--credentials-file",
                   help="JSON file containing credentials (generate with generate_credentials.py)")
    p.add_argument("--group-id",
                   help="GroupID in hex format (alternative to --credentials-file)")
    p.add_argument("--group-key",
                   help="GroupKey in hex format (alternative to --credentials-file)")
    p.add_argument("--timeout", type=float, default=5.0,
                   help="Timeout for API requests in seconds (default: 5.0)")
    p.add_argument("--use-https", action="store_true",
                   help="Use HTTPS instead of HTTP for API requests")
    p.add_argument("--retry-count", type=int, default=2,
                   help="Number of retries on failure (default: 2)")
    p.add_argument("--output", "-o", 
                   help="Output file for saving provisioned credentials")
    p.add_argument("--generate", action="store_true",
                   help="Generate new random credentials instead of using provided ones")
    p.add_argument("--skip-confirmation", action="store_true",
                   help="Skip confirmation prompts")
    return p


def _load_credentials_from_file(file_path: str) -> MieleCredentials:
    """Load credentials from a JSON file."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Check if file contains the expected fields
        if 'group_id' in data and 'group_key' in data:
            return MieleCredentials(
                group_id=data['group_id'],
                group_key=data['group_key']
            )
        else:
            raise ValueError("Credentials file does not contain required fields (group_id, group_key)")
    except (json.JSONDecodeError, IOError) as e:
        raise ValueError(f"Failed to load credentials from file: {str(e)}")


async def provision_and_output(args: argparse.Namespace) -> None:
    """Provision security credentials to a Miele device."""
    # Determine credentials to use
    if args.generate:
        logger.info("Generating new random credentials")
        credentials = MieleCredentials.generate_random()
    elif args.credentials_file:
        logger.info(f"Loading credentials from file: {args.credentials_file}")
        credentials = _load_credentials_from_file(args.credentials_file)
    elif args.group_id and args.group_key:
        logger.info("Using provided group ID and key")
        credentials = MieleCredentials(
            group_id=args.group_id,
            group_key=args.group_key
        )
    else:
        logger.error("No credentials provided. Use --generate, --credentials-file, or both --group-id and --group-key")
        sys.exit(1)
    
    # Show credentials to be used
    logger.info(f"Using GroupID: {credentials.get_id_hex()}")
    logger.info(f"Using GroupKey: {credentials.get_key_hex()[:8]}...{credentials.get_key_hex()[-8:]} (truncated for security)")
    
    # Confirm with user
    if not args.skip_confirmation:
        confirm = input("Proceed with provisioning? (y/n): ").strip().lower()
        if confirm != 'y':
            logger.info("Aborted by user")
            sys.exit(0)
    
    # Create setup client
    client = MieleSetupClient(timeout=args.timeout)
    
    # Provision credentials
    try:
        async with client:
            logger.info(f"Provisioning credentials to device at {args.host}")
            success = await client.provision_credentials(
                host=args.host,
                credentials=credentials,
                use_https=args.use_https,
                try_both_protocols=True,  # Try both HTTP and HTTPS
                retry_count=args.retry_count
            )
            
            if success:
                logger.info("Credential provisioning successful!")
                logger.info("The device is now securely configured with your credentials.")
                logger.info("You can now use the MieleClient to communicate with the device.")
                
                # Save credentials to file if requested
                if args.output:
                    with open(args.output, 'w') as f:
                        json.dump(credentials.model_dump(), f, indent=2)
                    logger.info(f"Credentials saved to: {args.output}")
            else:
                logger.error("Credential provisioning failed")
                sys.exit(1)
                
    except ProvisioningError as e:
        logger.error(f"Provisioning error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)


async def _async_main(args: argparse.Namespace) -> None:
    await provision_and_output(args)


def main():
    parser = _make_argparser()
    args = parser.parse_args()
    
    # Validate arguments
    if not args.generate and not args.credentials_file and not (args.group_id and args.group_key):
        parser.error("Either --generate, --credentials-file, or both --group-id and --group-key must be provided")
    
    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        logger.info("Aborted by user")
        sys.exit(2)


if __name__ == "__main__":
    main() 