"""
Device reset functionality for Miele devices.

This module provides functionality to handle device resets, including factory
reset detection and recovery procedures using the DOP2 protocol.
"""

import asyncio
import logging
from typing import Dict, Optional, Any, List, Tuple, Set, Callable, Awaitable
import time

from asyncmiele.api.client import MieleClient
from asyncmiele.exceptions.connection import DeviceResetError
from asyncmiele.models.device_profile import DeviceProfile
from asyncmiele.utils.discovery import discover_devices, get_device_info
from asyncmiele.dop2.binary import write_u8, write_u16, write_u32, pad_to_block_size

logger = logging.getLogger(__name__)


class DeviceResetter:
    """Handles device reset operations and recovery using DOP2 protocol.
    
    This class provides methods to detect when a device has been reset, initiate
    a reset using DOP2 XKM requests, and recover from a reset state.
    """
    
    # XKM Request types (from MieleRESTServer/MieleApi.py)
    XKM_NO_REQUEST = 0
    XKM_RESET = 1
    XKM_FACTORY_SETTINGS = 2
    XKM_SOFT_AP_CUSTOMER = 3
    XKM_SYSTEM_CREATE = 4
    
    # Device-specific SF Values for factory reset (fallback options)
    DEVICE_SPECIFIC_RESET_SF = {
        'washer': 12196,      # Washer_FactoryReset
        'dryer': 16001,       # Dryer_FactoryDefault
        'dishwasher': None,   # Not available - use XKM only
        'oven': None,         # Not available - use XKM only
        'hob': None,          # Induction hobs - very limited connectivity
        'unknown': None       # Use XKM only
    }
    
    def __init__(
        self,
        discovery_timeout: float = 10.0,
        recovery_timeout: float = 120.0,
        max_retries: int = 5
    ) -> None:
        """Initialize the device resetter.
        
        Args:
            discovery_timeout: Timeout for device discovery (seconds)
            recovery_timeout: Timeout for recovery operations (seconds)
            max_retries: Maximum number of retry attempts
        """
        self._discovery_timeout = discovery_timeout
        self._recovery_timeout = recovery_timeout
        self._max_retries = max_retries
        
        # Cache of known device MAC addresses
        self._device_macs: Dict[str, str] = {}
        
    async def detect_factory_reset(self, client: MieleClient, device_id: str) -> bool:
        """Detect if a device has been factory reset.
        
        Args:
            client: MieleClient instance
            device_id: ID of the device to check
            
        Returns:
            True if the device appears to have been reset
            
        Raises:
            DeviceResetError: If detection fails
        """
        try:
            # Try to get device information
            try:
                ident = await client.get_device_ident(device_id)
                # If we can get device ident, it's probably not reset
                return False
            except Exception:
                # If we can't get device ident, check if we can discover the device
                return await self._check_discovery(device_id)
                
        except Exception as e:
            raise DeviceResetError(f"Failed to detect factory reset for device {device_id}: {e}")
            
    async def _check_discovery(self, device_id: str) -> bool:
        """Check if a device is discoverable, which may indicate it's in reset mode.
        
        Args:
            device_id: ID of the device to check
            
        Returns:
            True if the device is discovered in reset mode
        """
        # If we have a MAC address cached, we can check if it appears in reset mode
        device_mac = self._device_macs.get(device_id)
        
        try:
            # Discover devices on the network
            devices = await discover_devices(timeout=self._discovery_timeout)
            
            if device_mac:
                # Check if we find a device with this MAC in setup mode
                for device_info in devices:
                    if device_info.get("mac") == device_mac and device_info.get("setup_mode", False):
                        return True
            else:
                # Without a MAC, we check if any device with the right ID is in setup mode
                for device_info in devices:
                    if device_info.get("id") == device_id and device_info.get("setup_mode", False):
                        # Cache the MAC for future checks
                        self._device_macs[device_id] = device_info.get("mac", "")
                        return True
                        
            return False
        except Exception as e:
            logger.error(f"Error during device discovery: {e}")
            return False
            
    async def recover_from_reset(
        self, 
        device_id: str, 
        profile: DeviceProfile
    ) -> Tuple[bool, Optional[MieleClient]]:
        """Attempt to recover a device after a reset.
        
        This method attempts to reconnect to a device after it has been reset,
        using the provided profile to re-establish the connection.
        
        Args:
            device_id: ID of the device
            profile: Device profile with configuration and credentials
            
        Returns:
            Tuple of (success, new_client)
            
        Raises:
            DeviceResetError: If recovery fails
        """
        logger.info(f"Attempting to recover device {device_id} from reset")
        
        # First, check if the device is in recovery/setup mode
        in_reset = await self._check_discovery(device_id)
        if not in_reset:
            logger.warning(f"Device {device_id} does not appear to be in reset mode")
            
        # Try to connect using the profile
        retries = 0
        while retries < self._max_retries:
            try:
                # Create a new client with the profile
                client = MieleClient.from_profile(profile)
                
                # Try to get device info to verify connection
                await client.get_device_ident(device_id)
                
                # If successful, return the client
                logger.info(f"Successfully recovered device {device_id}")
                return True, client
                
            except Exception as e:
                logger.warning(f"Recovery attempt {retries+1}/{self._max_retries} failed: {e}")
                retries += 1
                
                if retries < self._max_retries:
                    # Wait before retrying
                    await asyncio.sleep(2 ** retries)  # Exponential backoff
                    
        # If we get here, all recovery attempts failed
        logger.error(f"Failed to recover device {device_id} after {self._max_retries} attempts")
        return False, None
        
    async def initiate_reset(self, client: MieleClient, device_id: str) -> bool:
        """Initiate a device reset using DOP2 protocol.
        
        Args:
            client: MieleClient instance
            device_id: ID of the device to reset
            
        Returns:
            True if reset was initiated successfully
            
        Raises:
            DeviceResetError: If reset fails
        """
        logger.warning(f"Initiating factory reset for device {device_id} using DOP2 XKM protocol")
        
        try:
            # Cache the MAC address before reset if we don't have it
            if device_id not in self._device_macs:
                try:
                    # Get device info to cache MAC
                    device_info = await get_device_info(client.host)
                    if device_info and "mac" in device_info:
                        self._device_macs[device_id] = device_info["mac"]
                except Exception as e:
                    logger.warning(f"Failed to cache MAC address for device {device_id}: {e}")
            
            # Detect device type early for better error messaging
            device_type = await self._detect_device_type(client, device_id)
            if device_type == 'hob':
                logger.warning(f"Device {device_id} is an induction hob/cooktop")
                logger.warning("Induction hobs typically have very limited remote control capabilities")
                logger.warning("Factory reset may not be supported remotely and may require manual intervention")
            
            # Try DOP2 XKM approach first
            try:
                await self._send_xkm_factory_reset(client, device_id)
                return await self._wait_for_reset_mode(device_id)
            except DeviceResetError as e:
                logger.warning(f"DOP2 XKM reset failed: {e}")
                
                # For induction hobs, provide specific guidance
                if device_type == 'hob':
                    logger.error("Factory reset failed for induction hob. This is common because:")
                    logger.error("  - Induction hobs often don't support remote factory reset")
                    logger.error("  - They may require manual reset via physical controls")
                    logger.error("  - Some models only support basic network connectivity")
                    logger.error("Manual reset procedure:")
                    logger.error("  1. Check the device's settings menu on the control panel")
                    logger.error("  2. Look for 'Settings', 'Configuration', or 'Network' options")
                    logger.error("  3. Find 'Reset', 'Factory Settings', or 'Network Reset'")
                    logger.error("  4. Follow the on-screen instructions")
                    logger.error("  5. Some models may require holding specific button combinations")
                    return False
                
                # Try fallback approaches for other devices that don't support DOP2
                logger.info("Trying fallback reset methods for non-DOP2 devices...")
                return await self._try_fallback_reset_methods(client, device_id)
            
        except Exception as e:
            raise DeviceResetError(f"Failed to initiate reset for device {device_id}: {e}")
            
    async def _send_xkm_factory_reset(self, client: MieleClient, device_id: str) -> None:
        """Send the XKM factory reset command to the device via DOP2.
        
        Args:
            client: MieleClient instance
            device_id: ID of the device to reset
            
        Raises:
            DeviceResetError: If reset command fails
        """
        try:
            # First, discover what DOP2 endpoints are available
            available_endpoints = await self._discover_available_dop2_endpoints(client, device_id)
            
            if not available_endpoints:
                logger.warning("No accessible DOP2 endpoints found - device may not support DOP2 protocol")
                raise DeviceResetError("No accessible DOP2 endpoints found")
            
            # Build XKM FactorySettings payload
            # According to MieleRESTServer, XKM requests are sent via DOP2
            # The XKM_FACTORY_SETTINGS value is 2
            payload = self._build_xkm_payload(self.XKM_FACTORY_SETTINGS)
            
            logger.info(f"Sending XKM FactorySettings command to device {device_id}")
            logger.debug(f"XKM payload: {payload.hex()}")
            
            # Try XKM requests on available endpoints that might support system commands
            # Prioritize system unit (1) and core DOP2 unit (2) endpoints
            xkm_candidates = []
            
            # Add system unit candidates if available
            for unit, attr in available_endpoints:
                if unit == 1:  # System unit - most likely for XKM
                    xkm_candidates.append((unit, attr))
            
            # Add some specific XKM-likely endpoints even if not discovered
            potential_xkm = [
                (1, 1),    # System unit, basic command
                (1, 5),    # System unit, extended command
                (1, 10),   # System unit, management command
                (2, 300),  # DOP2 unit, program selection (sometimes used for commands)
            ]
            
            for unit, attr in potential_xkm:
                if (unit, attr) not in xkm_candidates:
                    xkm_candidates.append((unit, attr))
            
            reset_sent = False
            for unit, attribute in xkm_candidates:
                try:
                    logger.debug(f"Attempting XKM reset via DOP2 unit {unit}, attribute {attribute}")
                    await client.write_dop2_leaf(device_id, unit, attribute, payload)
                    
                    logger.info(f"XKM FactorySettings command sent successfully via unit {unit}, attribute {attribute}")
                    reset_sent = True
                    break
                    
                except Exception as e:
                    logger.debug(f"XKM reset attempt failed for unit {unit}, attribute {attribute}: {e}")
                    continue
            
            if not reset_sent:
                # Fallback: try device-specific SF values if available
                device_type = await self._detect_device_type(client, device_id)
                sf_value = self.DEVICE_SPECIFIC_RESET_SF.get(device_type)
                
                if sf_value:
                    logger.info(f"Falling back to device-specific SF value {sf_value} for {device_type}")
                    sf_payload = self._build_sf_value_payload(1)  # Value 1 to trigger reset
                    
                    # Try to write to SF Value endpoint if it's available
                    sf_endpoints = [(2, 105)]  # Standard SF Value endpoint
                    if (2, 105) in available_endpoints:
                        try:
                            await client.write_dop2_leaf(device_id, 2, sf_value, sf_payload)
                            logger.info(f"Device-specific factory reset command sent via SF value {sf_value}")
                            reset_sent = True
                        except Exception as e:
                            logger.debug(f"SF value reset attempt failed: {e}")
                    
            if not reset_sent:
                # Last resort: try a direct approach with simpler payloads
                logger.info("Trying last resort: simple command payloads on available endpoints")
                simple_payloads = [
                    bytes([0x02, 0x00]),  # Simple XKM FactorySettings
                    bytes([0x01, 0x00]),  # Simple reset command
                    bytes([0xFF, 0xFF]),  # Reset trigger
                ]
                
                for payload_attempt in simple_payloads:
                    padded_payload = self._pad_simple_payload(payload_attempt)
                    for unit, attr in available_endpoints[:3]:  # Try first 3 available endpoints
                        try:
                            logger.debug(f"Trying simple payload {payload_attempt.hex()} on unit {unit}, attr {attr}")
                            await client.write_dop2_leaf(device_id, unit, attr, padded_payload)
                            logger.info(f"Simple reset command sent successfully via unit {unit}, attribute {attr}")
                            reset_sent = True
                            break
                        except Exception as e:
                            logger.debug(f"Simple payload attempt failed for unit {unit}, attribute {attr}: {e}")
                            continue
                    if reset_sent:
                        break
                        
            if not reset_sent:
                raise DeviceResetError("Failed to send factory reset command via any known method")
                
        except Exception as e:
            raise DeviceResetError(f"Failed to send XKM factory reset command: {e}")
    
    def _pad_simple_payload(self, payload: bytes) -> bytes:
        """Pad a simple payload for DOP2 transmission.
        
        Args:
            payload: Simple payload bytes
            
        Returns:
            Padded payload ready for transmission
        """
        # Ensure minimum length and pad to 16-byte boundary
        padded = bytearray(payload)
        while len(padded) < 16:
            padded.append(0x20)  # Pad with spaces
        return bytes(padded)
        
    def _build_xkm_payload(self, xkm_request_type: int) -> bytes:
        """Build XKM request payload for DOP2.
        
        Args:
            xkm_request_type: Type of XKM request (e.g., XKM_FACTORY_SETTINGS = 2)
            
        Returns:
            Binary payload for DOP2 write
        """
        # XKM requests appear to be simple integer values
        # Based on MieleRESTServer, the format is straightforward
        payload = bytearray()
        
        # Write the XKM request type as a 16-bit value
        payload += write_u16(xkm_request_type)
        
        # Pad to 16-byte boundary for AES encryption
        return pad_to_block_size(bytes(payload))
        
    def _build_sf_value_payload(self, value: int) -> bytes:
        """Build SF Value payload for DOP2.
        
        Args:
            value: Value to set (typically 1 to trigger action)
            
        Returns:
            Binary payload for DOP2 write
        """
        payload = bytearray()
        
        # Write the value as a 32-bit integer
        payload += write_u32(value)
        
        # Pad to 16-byte boundary for AES encryption
        return pad_to_block_size(bytes(payload))
        
    async def _detect_device_type(self, client: MieleClient, device_id: str) -> str:
        """Detect the device type for fallback SF value selection.
        
        Args:
            client: MieleClient instance
            device_id: ID of the device
            
        Returns:
            Device type string ('washer', 'dryer', 'dishwasher', 'oven', 'unknown')
        """
        try:
            device = await client.get_device(device_id)
            if device and device.ident:
                device_type = device.ident.device_type.lower()
                
                # Map device type strings to our categories
                if any(keyword in device_type for keyword in ['washer', 'washing', 'wasch']):
                    return 'washer'
                elif any(keyword in device_type for keyword in ['dryer', 'tumble', 'trockner']):
                    return 'dryer'
                elif any(keyword in device_type for keyword in ['dishwasher', 'spül', 'geschirrspüler']):
                    return 'dishwasher'
                elif any(keyword in device_type for keyword in ['oven', 'backofen', 'range']):
                    return 'oven'
                elif any(keyword in device_type for keyword in ['hob', 'induction', 'cooktop', 'kochfeld']):
                    return 'hob'
                    
        except Exception as e:
            logger.warning(f"Failed to detect device type for {device_id}: {e}")
            
        return 'unknown'
        
    async def _discover_available_dop2_endpoints(self, client: MieleClient, device_id: str) -> List[Tuple[int, int]]:
        """Discover available DOP2 endpoints by testing common ones.
        
        Args:
            client: MieleClient instance
            device_id: ID of the device
            
        Returns:
            List of (unit, attribute) tuples that are accessible
        """
        available_endpoints = []
        
        # Common DOP2 endpoints to test
        test_endpoints = [
            # System unit endpoints
            (1, 2),    # System info
            (1, 3),    # System status  
            (1, 4),    # System config
            # Core DOP2 endpoints
            (2, 105),  # SF Value
            (2, 119),  # Hours of operation
            (2, 138),  # Cycle counter
            (2, 256),  # Combined state
            (2, 286),  # Device state
            (2, 293),  # Device ident
            # Legacy endpoints
            (14, 1570), # Legacy program list
        ]
        
        logger.debug(f"Discovering available DOP2 endpoints for device {device_id}")
        
        for unit, attribute in test_endpoints:
            try:
                # Try to read from this endpoint - just to see if it exists
                await client.read_dop2_leaf(device_id, unit, attribute)
                available_endpoints.append((unit, attribute))
                logger.debug(f"✓ DOP2 unit {unit}, attribute {attribute} is accessible")
            except Exception:
                logger.debug(f"✗ DOP2 unit {unit}, attribute {attribute} is not accessible")
                continue
                
        logger.info(f"Found {len(available_endpoints)} accessible DOP2 endpoints")
        return available_endpoints
        
    async def _wait_for_reset_mode(self, device_id: str) -> bool:
        """Wait for the device to enter reset/setup mode.
        
        Args:
            device_id: ID of the device
            
        Returns:
            True if the device entered reset mode
        """
        logger.info(f"Waiting for device {device_id} to enter reset mode")
        
        start_time = time.time()
        
        while time.time() - start_time < self._recovery_timeout:
            # Check if device is discoverable in setup mode
            if await self._check_discovery(device_id):
                logger.info(f"Device {device_id} is now in reset mode")
                return True
                
            # Wait before checking again
            await asyncio.sleep(5)
            
        logger.warning(f"Timeout waiting for device {device_id} to enter reset mode")
        return False
        
    def register_device_mac(self, device_id: str, mac_address: str) -> None:
        """Register a device MAC address for future reference.
        
        Args:
            device_id: ID of the device
            mac_address: MAC address of the device
        """
        self._device_macs[device_id] = mac_address 
        
    async def _try_fallback_reset_methods(self, client: MieleClient, device_id: str) -> bool:
        """Try fallback reset methods for devices that don't support DOP2.
        
        Args:
            client: MieleClient instance
            device_id: ID of the device to reset
            
        Returns:
            True if reset was initiated successfully
        """
        logger.info(f"Attempting fallback reset methods for device {device_id}")
        
        # Method 1: Try the original REST API reset endpoints
        rest_endpoints = [
            f"/devices/{device_id}/actions/reset",
            f"/devices/{device_id}/actions/factory-reset", 
            f"/devices/{device_id}/reset",
            f"/devices/{device_id}/factory-reset",
            f"/Devices/{device_id}/actions/reset",
            f"/Devices/{device_id}/Actions/Reset",
        ]
        
        reset_payloads = [
            {"type": "factory"},
            {"action": "factory_reset"},
            {"reset_type": "factory"},
            {"command": "factory_reset"},
            {},  # Empty payload
        ]
        
        # Try REST endpoints
        for endpoint in rest_endpoints:
            for payload in reset_payloads:
                try:
                    logger.debug(f"Trying REST endpoint {endpoint} with payload {payload}")
                    result = await client._put_request(endpoint, payload)
                    logger.info(f"REST reset command sent successfully to {endpoint}")
                    return await self._wait_for_reset_mode(device_id)
                except Exception as e:
                    logger.debug(f"REST endpoint {endpoint} failed: {e}")
                    continue
        
        # Method 2: Try system-level commands via simple HTTP requests
        system_endpoints = [
            "/system/reset",
            "/system/factory-reset",
            "/reset",
            "/factory-reset",
            "/reboot?factory=true",
        ]
        
        for endpoint in system_endpoints:
            try:
                logger.debug(f"Trying system endpoint {endpoint}")
                result = await client._put_request(endpoint, {})
                logger.info(f"System reset command sent successfully to {endpoint}")
                return await self._wait_for_reset_mode(device_id)
            except Exception as e:
                logger.debug(f"System endpoint {endpoint} failed: {e}")
                continue
        
        # Method 3: Try sending a raw HTTP request that might trigger reset
        try:
            logger.debug("Trying raw reset command")
            # Some devices respond to simple GET/POST requests to specific endpoints
            raw_endpoints = [
                "/cgi-bin/reset",
                "/admin/reset", 
                "/config/reset",
                "/setup/reset",
            ]
            
            for endpoint in raw_endpoints:
                try:
                    result = await client._get_request(endpoint)
                    logger.info(f"Raw reset command sent successfully to {endpoint}")
                    return await self._wait_for_reset_mode(device_id)
                except Exception as e:
                    logger.debug(f"Raw endpoint {endpoint} failed: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"Raw HTTP reset attempts failed: {e}")
        
        # Method 4: Try sending the reset command to different device IDs or broadcast
        alternative_targets = [
            "all",
            "broadcast", 
            "*",
            "0",
            "system",
        ]
        
        for target in alternative_targets:
            try:
                endpoint = f"/devices/{target}/actions/reset"
                logger.debug(f"Trying broadcast reset to {endpoint}")
                result = await client._put_request(endpoint, {"type": "factory", "target": device_id})
                logger.info(f"Broadcast reset command sent successfully")
                return await self._wait_for_reset_mode(device_id)
            except Exception as e:
                logger.debug(f"Broadcast reset to {target} failed: {e}")
                continue
        
        logger.error(f"All fallback reset methods failed for device {device_id}")
        logger.info("The device may not support remote factory reset, or may require:")
        logger.info("  - Manual confirmation via device display")
        logger.info("  - Physical button press on the device")
        logger.info("  - Different authentication or device state")
        logger.info("  - Device-specific reset procedure")
        
        return False 