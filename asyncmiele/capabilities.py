"""
Device capability detection and management.

This module provides functionality to detect and manage Miele device capabilities,
allowing for adaptive behavior based on the actual features supported by each device.
"""

from enum import Flag, auto
from typing import Dict, Set, List, Optional, Any
import logging

from asyncmiele.enums import DeviceType

logger = logging.getLogger(__name__)


class DeviceCapability(Flag):
    """Capabilities that a Miele device may support."""
    NONE = 0
    
    # Basic capabilities
    STATE_REPORTING = auto()       # Device can report its state
    PROGRAM_REPORTING = auto()     # Device can report current program
    
    # Control capabilities
    WAKE_UP = auto()               # Device supports wake-up commands
    REMOTE_START = auto()          # Device supports remote start control
    REMOTE_CONTROL = auto()        # Device supports remote control
    
    # Program capabilities
    PROGRAM_CATALOG = auto()       # Device has a program catalog
    PROGRAM_SELECTION = auto()     # Device supports program selection
    PARAMETER_SELECTION = auto()   # Device supports parameter selection
    
    # DOP2 capabilities
    DOP2_BASIC = auto()            # Device supports basic DOP2 access
    DOP2_ADVANCED = auto()         # Device supports advanced DOP2 features
    
    # Data capabilities
    CONSUMPTION_STATS = auto()     # Device provides consumption statistics


# Predefined capability sets for different device types
DEFAULT_CAPABILITIES = {
    DeviceType.WashingMachine: (
        DeviceCapability.STATE_REPORTING |
        DeviceCapability.PROGRAM_REPORTING |
        DeviceCapability.WAKE_UP |
        DeviceCapability.REMOTE_START |
        DeviceCapability.PROGRAM_CATALOG |
        DeviceCapability.DOP2_BASIC
    ),
    DeviceType.TumbleDryer: (
        DeviceCapability.STATE_REPORTING |
        DeviceCapability.PROGRAM_REPORTING |
        DeviceCapability.WAKE_UP |
        DeviceCapability.REMOTE_START |
        DeviceCapability.PROGRAM_CATALOG |
        DeviceCapability.DOP2_BASIC
    ),
    DeviceType.Dishwasher: (
        DeviceCapability.STATE_REPORTING |
        DeviceCapability.PROGRAM_REPORTING |
        DeviceCapability.WAKE_UP |
        DeviceCapability.REMOTE_START |
        DeviceCapability.PROGRAM_CATALOG |
        DeviceCapability.DOP2_BASIC
    ),
    DeviceType.Oven: (
        DeviceCapability.STATE_REPORTING |
        DeviceCapability.PROGRAM_REPORTING |
        DeviceCapability.WAKE_UP |
        DeviceCapability.REMOTE_START |
        DeviceCapability.PROGRAM_CATALOG |
        DeviceCapability.DOP2_BASIC
    ),
    # Default for unknown devices - minimal capabilities
    DeviceType.NoUse: (
        DeviceCapability.STATE_REPORTING
    )
}


class DeviceCapabilityDetector:
    """
    Detects and tracks capabilities of Miele devices.
    
    This class provides methods to detect what capabilities a device supports,
    both through predefined profiles and runtime detection.
    """
    
    def __init__(self):
        """Initialize the capability detector."""
        # Device ID -> Detected capabilities
        self._detected_capabilities: Dict[str, DeviceCapability] = {}
        
        # Device ID -> Failed capability tests
        self._failed_tests: Dict[str, Set[DeviceCapability]] = {}
    
    def get_initial_capabilities(self, device_type: DeviceType) -> DeviceCapability:
        """
        Get the initial capability set for a device based on its type.
        
        Args:
            device_type: The type of the device
            
        Returns:
            The initial capabilities for the device type
        """
        return DEFAULT_CAPABILITIES.get(device_type, DEFAULT_CAPABILITIES[DeviceType.NoUse])
    
    def get_capabilities(self, device_id: str, device_type: DeviceType) -> DeviceCapability:
        """
        Get the detected capabilities for a device.
        
        If the device has not been seen before, returns the default capabilities
        for its device type.
        
        Args:
            device_id: The ID of the device
            device_type: The type of the device
            
        Returns:
            The detected capabilities for the device
        """
        if device_id not in self._detected_capabilities:
            self._detected_capabilities[device_id] = self.get_initial_capabilities(device_type)
        
        return self._detected_capabilities[device_id]
    
    def record_capability_test(
        self, 
        device_id: str, 
        capability: DeviceCapability, 
        success: bool
    ) -> None:
        """
        Record the result of a capability test.
        
        Args:
            device_id: The ID of the device
            capability: The capability that was tested
            success: Whether the test was successful
        """
        if device_id not in self._detected_capabilities:
            # Initialize with empty capabilities if not seen before
            self._detected_capabilities[device_id] = DeviceCapability.NONE
        
        if device_id not in self._failed_tests:
            self._failed_tests[device_id] = set()
            
        if success:
            # Add the capability
            self._detected_capabilities[device_id] |= capability
            # Remove from failed tests if it was there
            self._failed_tests[device_id].discard(capability)
        else:
            # Add to failed tests
            self._failed_tests[device_id].add(capability)
            # Remove the capability
            self._detected_capabilities[device_id] &= ~capability
            
        logger.debug(f"Device {device_id} capability {capability.name}: {'✓' if success else '✗'}")
    
    def has_capability(self, device_id: str, capability: DeviceCapability) -> bool:
        """
        Check if a device has a specific capability.
        
        Args:
            device_id: The ID of the device
            capability: The capability to check
            
        Returns:
            True if the device has the capability, False otherwise
        """
        if device_id not in self._detected_capabilities:
            return False
        
        return bool(self._detected_capabilities[device_id] & capability)
    
    def reset_capabilities(self, device_id: str) -> None:
        """
        Reset all detected capabilities for a device.
        
        This might be needed after a device firmware update or reconfiguration.
        
        Args:
            device_id: The ID of the device
        """
        if device_id in self._detected_capabilities:
            del self._detected_capabilities[device_id]
        
        if device_id in self._failed_tests:
            del self._failed_tests[device_id]
    
    def get_failed_tests(self, device_id: str) -> Set[DeviceCapability]:
        """
        Get the set of capabilities that failed testing for a device.
        
        Args:
            device_id: The ID of the device
            
        Returns:
            Set of capabilities that failed testing
        """
        return self._failed_tests.get(device_id, set())


# Global capability detector instance
detector = DeviceCapabilityDetector()


def test_capability(capability: DeviceCapability):
    """
    Decorator for methods that test a specific capability.
    
    This decorator wraps a method to record whether a capability test succeeded or failed.
    
    Args:
        capability: The capability being tested
        
    Returns:
        Decorated function
    """
    def decorator(func):
        async def wrapper(client, device_id, *args, **kwargs):
            try:
                result = await func(client, device_id, *args, **kwargs)
                # Record successful test
                detector.record_capability_test(device_id, capability, True)
                return result
            except Exception as e:
                # Record failed test
                detector.record_capability_test(device_id, capability, False)
                # Re-raise the exception
                raise
        return wrapper
    return decorator 