#!/usr/bin/env python3
"""
Configure WiFi settings for a Miele device in setup mode.

This script provides a command-line interface for configuring a Miele device's
WiFi settings when it's in setup mode.
"""

import argparse
import asyncio
import json
import sys
import logging
from typing import Dict, Any, Optional

from asyncmiele.api.setup_client import MieleSetupClient
from asyncmiele.models.network_config import MieleNetworkConfig, SecurityType
from asyncmiele.utils.provisioning import detect_setup_mode_ssid, connect_to_miele_ap, get_default_ap_password
from asyncmiele.exceptions.setup import AccessPointConnectionError, WifiConfigurationError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def _make_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Configure WiFi settings for a Miele device in setup mode"
    )
    p.add_argument("--ssid", required=True,
                   help="SSID of the WiFi network to configure the device to connect to")
    p.add_argument("--password", required=False,
                   help="Password for the WiFi network (required for WPA/WPA2 networks)")
    p.add_argument("--security", choices=["none", "wep", "wpa", "wpa2", "wpa2psk", "wpawpa2"],
                   default="wpa2", help="Security type of the WiFi network (default: wpa2)")
    p.add_argument("--hidden", action="store_true",
                   help="Indicate that the WiFi network is hidden")
    p.add_argument("--ap-host", default="192.168.1.1",
                   help="IP address of the device in setup mode (default: 192.168.1.1)")
    p.add_argument("--ap-ssid",
                   help="SSID of the Miele access point to connect to (if not already connected)")
    p.add_argument("--ap-password",
                   help="Password for the Miele access point (if needed)")
    p.add_argument("--timeout", type=float, default=5.0,
                   help="Timeout for API requests in seconds (default: 5.0)")
    p.add_argument("--use-https", action="store_true",
                   help="Use HTTPS instead of HTTP for API requests")
    p.add_argument("--retry-count", type=int, default=2,
                   help="Number of retries on failure (default: 2)")
    p.add_argument("--auto-connect", action="store_true",
                   help="Automatically connect to Miele access point if detected")
    p.add_argument("--scan", action="store_true",
                   help="Scan for Miele access points")
    return p


def _security_type_from_arg(security_arg: str) -> SecurityType:
    """Convert command-line security argument to SecurityType enum."""
    security_map = {
        "none": SecurityType.NONE,
        "wep": SecurityType.WEP,
        "wpa": SecurityType.WPA_PSK,
        "wpa2": SecurityType.WPA2,
        "wpa2psk": SecurityType.WPA2_PSK,
        "wpawpa2": SecurityType.WPA_WPA2_PSK,
    }
    return security_map.get(security_arg.lower(), SecurityType.WPA2)


async def configure_and_output(args: argparse.Namespace) -> None:
    """Configure WiFi settings for a Miele device."""
    # First, check if we need to scan for Miele access points
    if args.scan:
        logger.info("Scanning for Miele access points...")
        miele_ssids = detect_setup_mode_ssid()
        if miele_ssids:
            logger.info(f"Found Miele access points: {', '.join(miele_ssids)}")
            if args.auto_connect and not args.ap_ssid:
                # Auto-connect to the first Miele access point found
                args.ap_ssid = miele_ssids[0]
                logger.info(f"Auto-connecting to: {args.ap_ssid}")
        else:
            logger.info("No Miele access points found")
            if args.auto_connect:
                logger.error("Cannot auto-connect: No Miele access points found")
                sys.exit(1)
    
    # If ap_ssid is specified, try to connect to it
    if args.ap_ssid:
        logger.info(f"Connecting to Miele access point: {args.ap_ssid}")
        password = args.ap_password
        
        # If no password provided, try to use the default password
        if not password:
            password = get_default_ap_password(args.ap_ssid)
        
        try:
            connect_to_miele_ap(args.ap_ssid, password)
            logger.info(f"Successfully connected to {args.ap_ssid}")
        except AccessPointConnectionError as e:
            logger.error(f"Failed to connect to Miele access point: {str(e)}")
            sys.exit(1)
    
    # Create network configuration
    security_type = _security_type_from_arg(args.security)
    network_config = MieleNetworkConfig(
        ssid=args.ssid,
        security_type=security_type,
        password=args.password,
        hidden=args.hidden
    )
    
    # Create setup client
    client = MieleSetupClient(
        host=args.ap_host,
        timeout=args.timeout
    )
    
    # Configure WiFi
    try:
        async with client:
            logger.info(f"Configuring device at {args.ap_host} to connect to network: {args.ssid}")
            success = await client.configure_wifi(
                network_config=network_config,
                use_https=args.use_https,
                retry_count=args.retry_count
            )
            
            if success:
                logger.info("WiFi configuration successful!")
                logger.info(f"The device will now connect to: {args.ssid}")
                logger.info("Note: The device may take some time to connect to the network.")
                logger.info("After connection, the device will no longer be accessible via its access point.")
            else:
                logger.error("WiFi configuration failed")
                sys.exit(1)
                
    except WifiConfigurationError as e:
        logger.error(f"WiFi configuration error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)


async def _async_main(args: argparse.Namespace) -> None:
    await configure_and_output(args)


def main():
    parser = _make_argparser()
    args = parser.parse_args()
    
    # Validate arguments
    if args.security.lower() != "none" and not args.password:
        parser.error("Password is required for secured WiFi networks")
    
    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        logger.info("Aborted by user")
        sys.exit(2)


if __name__ == "__main__":
    main() 