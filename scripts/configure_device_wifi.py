#!/usr/bin/env python3
"""
Configure WiFi settings for a Miele device in setup mode.

This script provides a command-line interface for configuring a Miele device's
WiFi settings when it's in setup mode.

This script assumes that connection to the device's WiFi access point has 
already been established manually.

USAGE:
    1. Manually connect to the Miele device's WiFi access point
       (usually named something like "Miele_XXXXXX")
    
    2. Run this script to configure the device's WiFi:
       python configure_device_wifi.py --ssid "MyWiFi" --password "mypassword"
    
    3. The device will disconnect from its access point and connect to your WiFi

This script mimics the exact behavior of the MieleRESTServer provision-wifi.sh script,
which uses a simple HTTP PUT request to the /WLAN endpoint with JSON payload.

Example payload sent to device:
    {"SSID": "MyWiFi", "Sec": "WPA2", "Key": "mypassword"}
"""

import argparse
import asyncio
import json
import sys
import logging
from typing import Dict, Any, Optional

import aiohttp

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
    p.add_argument("--security", choices=["None", "WEP", "WPA-PSK", "WPA2", "WPA2-PSK", "WPA/WPA2-PSK"],
                   default="WPA2", help="Security type of the WiFi network (default: WPA2)")
    p.add_argument("--device-ip", default="192.168.1.1",
                   help="IP address of the device in setup mode (default: 192.168.1.1)")
    p.add_argument("--timeout", type=float, default=10.0,
                   help="Timeout for API requests in seconds (default: 10.0)")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be sent without actually sending it")
    return p


async def configure_wifi_simple(device_ip: str, ssid: str, security: str, password: Optional[str], timeout: float, dry_run: bool = False) -> bool:
    """
    Configure WiFi settings using the exact same approach as MieleRESTServer.
    
    This mimics the wget command:
    wget -O - --method=PUT --body-file=wifi.json 192.168.1.1/WLAN
    
    Args:
        device_ip: IP address of the device
        ssid: WiFi network SSID
        security: Security type (None, WEP, WPA-PSK, WPA2, WPA2-PSK, WPA/WPA2-PSK)
        password: WiFi password (None for open networks)
        timeout: Request timeout in seconds
        dry_run: If True, only show what would be sent without sending it
        
    Returns:
        True if configuration was successful (or if dry_run is True)
    """
    # Prepare the JSON payload exactly like MieleRESTServer
    wifi_config = {
        "SSID": ssid,
        "Sec": security,
    }
    
    # Only include Key if password is provided and security is not None
    if security != "None" and password:
        wifi_config["Key"] = password
    
    url = f"http://{device_ip}/WLAN"
    
    logger.info(f"Configuring WiFi on device at {device_ip}")
    logger.info(f"Network: {ssid} (Security: {security})")
    logger.info(f"URL: {url}")
    logger.info(f"Payload: {json.dumps(wifi_config, indent=2)}")
    
    if dry_run:
        logger.info("DRY RUN: Not actually sending the request")
        return True
    
    try:
        # Create HTTP session with specific timeout
        timeout_config = aiohttp.ClientTimeout(total=timeout)
        
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            # Send PUT request with JSON payload
            async with session.put(
                url,
                json=wifi_config,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "MieleWiFiConfig/1.0"
                }
            ) as response:
                
                # Log the response
                response_text = await response.text()
                logger.info(f"Response status: {response.status}")
                logger.info(f"Response body: {response_text}")
                
                # Consider any 2xx status as success
                if 200 <= response.status < 300:
                    logger.info("WiFi configuration successful!")
                    logger.info(f"Device will connect to network: {ssid}")
                    logger.info("Note: The device may take some time to connect to the network.")
                    logger.info("After connection, the device will no longer be accessible via its access point.")
                    return True
                else:
                    logger.error(f"WiFi configuration failed with status {response.status}")
                    logger.error(f"Response: {response_text}")
                    return False
                    
    except aiohttp.ClientConnectorError as e:
        logger.error(f"Failed to connect to device at {device_ip}: {e}")
        logger.error("Make sure you are connected to the device's WiFi access point")
        return False
    except aiohttp.ClientError as e:
        logger.error(f"HTTP request failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False


async def configure_and_output(args: argparse.Namespace) -> None:
    """Configure WiFi settings for a Miele device."""
    
    # Validate that password is provided for secured networks
    if args.security != "None" and not args.password:
        logger.error(f"Password is required for {args.security} networks")
        sys.exit(1)
    
    # Configure WiFi using the simple approach
    success = await configure_wifi_simple(
        device_ip=args.device_ip,
        ssid=args.ssid,
        security=args.security,
        password=args.password,
        timeout=args.timeout,
        dry_run=args.dry_run
    )
    
    if not success:
        logger.error("WiFi configuration failed")
        sys.exit(1)


async def _async_main(args: argparse.Namespace) -> None:
    await configure_and_output(args)


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