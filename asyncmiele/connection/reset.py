"""
Device reset functionality for Miele devices.

This module provides functionality to handle device resets, including factory
reset detection and recovery procedures.
"""

import asyncio
import logging
from typing import Dict, Optional, Any, List, Tuple, Set, Callable, Awaitable
import time

from asyncmiele.api.client import MieleClient
from asyncmiele.exceptions.connection import DeviceResetError
from asyncmiele.models.device_profile import DeviceProfile
from asyncmiele.utils.discovery import discover_devices, get_device_info

logger = logging.getLogger(__name__)


class DeviceResetter:
    """Handles device reset operations and recovery.
    
    This class provides methods to detect when a device has been reset, initiate
    a reset, and recover from a reset state.
    """
    
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
        """Initiate a device reset.
        
        Args:
            client: MieleClient instance
            device_id: ID of the device to reset
            
        Returns:
            True if reset was initiated successfully
            
        Raises:
            DeviceResetError: If reset fails
        """
        logger.warning(f"Initiating reset for device {device_id}")
        
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
            
            # Send reset command to device
            # Note: This is a placeholder for the actual reset method
            # The specific reset API endpoint might vary by device
            await self._send_reset_command(client, device_id)
            
            # Wait for the device to reset and enter setup mode
            return await self._wait_for_reset_mode(device_id)
            
        except Exception as e:
            raise DeviceResetError(f"Failed to initiate reset for device {device_id}: {e}")
            
    async def _send_reset_command(self, client: MieleClient, device_id: str) -> None:
        """Send the reset command to the device.
        
        This is a placeholder for the actual reset command implementation.
        
        Args:
            client: MieleClient instance
            device_id: ID of the device to reset
            
        Raises:
            DeviceResetError: If reset command fails
        """
        # Note: This is an example implementation
        # The actual reset command would need to be determined from Miele documentation
        try:
            # Attempt to send reset command - this is a placeholder
            # For some devices, this might be a PUT to a specific endpoint
            await client._put_request(f"/devices/{device_id}/actions/reset", {"type": "factory"})
            
            # Another approach might be via DOP2 (if supported)
            # await client.dop2_write_leaf(device_id, 2, 9999, b"\x01", idx1=1, idx2=0)
            
            logger.info(f"Reset command sent to device {device_id}")
            
        except Exception as e:
            raise DeviceResetError(f"Failed to send reset command: {e}")
            
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