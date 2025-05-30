"""
Device capability detection and management for Miele appliances.

This module provides functionality to detect what capabilities a device supports,
track capability test results, and provide capability-based feature gating.
"""

import logging
from enum import Flag, auto
from typing import Dict, Set, Tuple, TYPE_CHECKING
from functools import wraps

from asyncmiele.enums import DeviceTypeMiele as DeviceType

if TYPE_CHECKING:
    from asyncmiele.api.client import MieleClient

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


# Predefined capability sets for different device types (converted to sets)
DEFAULT_CAPABILITIES = {
    DeviceType.WashingMachine: {
        DeviceCapability.STATE_REPORTING,
        DeviceCapability.PROGRAM_REPORTING,
        DeviceCapability.WAKE_UP,
        DeviceCapability.REMOTE_START,
        DeviceCapability.PROGRAM_CATALOG,
        DeviceCapability.DOP2_BASIC
    },
    DeviceType.TumbleDryer: {
        DeviceCapability.STATE_REPORTING,
        DeviceCapability.PROGRAM_REPORTING,
        DeviceCapability.WAKE_UP,
        DeviceCapability.REMOTE_START,
        DeviceCapability.PROGRAM_CATALOG,
        DeviceCapability.DOP2_BASIC
    },
    DeviceType.Dishwasher: {
        DeviceCapability.STATE_REPORTING,
        DeviceCapability.PROGRAM_REPORTING,
        DeviceCapability.WAKE_UP,
        DeviceCapability.REMOTE_START,
        DeviceCapability.PROGRAM_CATALOG,
        DeviceCapability.DOP2_BASIC
    },
    DeviceType.Oven: {
        DeviceCapability.STATE_REPORTING,
        DeviceCapability.PROGRAM_REPORTING,
        DeviceCapability.WAKE_UP,
        DeviceCapability.REMOTE_START,
        DeviceCapability.PROGRAM_CATALOG,
        DeviceCapability.DOP2_BASIC
    },
    # Default for unknown devices - minimal capabilities
    DeviceType.NoUse: {
        DeviceCapability.STATE_REPORTING
    }
}


class DeviceCapabilityDetector:
    """
    Detects and tracks capabilities of Miele devices.
    
    Enhanced for Set-based capability operations and DeviceProfile integration.
    This class provides methods to detect what capabilities a device supports,
    both through predefined profiles and runtime detection.
    """
    
    def __init__(self):
        """Initialize the capability detector."""
        # Device ID -> Detected capabilities (as sets)
        self._detected_capabilities: Dict[str, Set[DeviceCapability]] = {}
        
        # Device ID -> Failed capability tests (as sets)
        self._failed_tests: Dict[str, Set[DeviceCapability]] = {}
    
    def get_initial_capabilities(self, device_type: DeviceType) -> Set[DeviceCapability]:
        """
        Get the initial capability set for a device based on its type.
        
        Args:
            device_type: The type of the device
            
        Returns:
            The initial capabilities set for the device type
        """
        return DEFAULT_CAPABILITIES.get(device_type, DEFAULT_CAPABILITIES[DeviceType.NoUse]).copy()
    
    def get_capabilities(self, device_id: str, device_type: DeviceType) -> Set[DeviceCapability]:
        """
        Get the detected capabilities for a device as a set.
        
        If the device has not been seen before, returns the default capabilities
        for its device type.
        
        Args:
            device_id: The ID of the device
            device_type: The type of the device
            
        Returns:
            The detected capabilities set for the device
        """
        if device_id not in self._detected_capabilities:
            self._detected_capabilities[device_id] = self.get_initial_capabilities(device_type)
        
        return self._detected_capabilities[device_id].copy()
    
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
            self._detected_capabilities[device_id] = set()
        
        if device_id not in self._failed_tests:
            self._failed_tests[device_id] = set()
            
        if success:
            # Add the capability
            self._detected_capabilities[device_id].add(capability)
            # Remove from failed tests if it was there
            self._failed_tests[device_id].discard(capability)
        else:
            # Add to failed tests
            self._failed_tests[device_id].add(capability)
            # Remove the capability
            self._detected_capabilities[device_id].discard(capability)
            
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
        
        return capability in self._detected_capabilities[device_id]
    
    def has_any_capability(self, device_id: str, *capabilities: DeviceCapability) -> bool:
        """
        Check if a device has any of the specified capabilities.
        
        Args:
            device_id: The ID of the device
            *capabilities: The capabilities to check
            
        Returns:
            True if the device has any of the capabilities, False otherwise
        """
        if device_id not in self._detected_capabilities:
            return False
        
        return bool(self._detected_capabilities[device_id].intersection(capabilities))
    
    def has_all_capabilities(self, device_id: str, *capabilities: DeviceCapability) -> bool:
        """
        Check if a device has all of the specified capabilities.
        
        Args:
            device_id: The ID of the device
            *capabilities: The capabilities to check
            
        Returns:
            True if the device has all of the capabilities, False otherwise
        """
        if device_id not in self._detected_capabilities:
            return False
        
        return set(capabilities).issubset(self._detected_capabilities[device_id])
    
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
        return self._failed_tests.get(device_id, set()).copy()
    
    def detect_capabilities_as_sets(self, device_id: str, device_type: DeviceType) -> Tuple[Set[DeviceCapability], Set[DeviceCapability]]:
        """
        Get detected capabilities as a tuple of sets.
        
        Args:
            device_id: The ID of the device
            device_type: The type of the device
            
        Returns:
            Tuple of (supported_capabilities, failed_capabilities) as sets
        """
        supported = self.get_capabilities(device_id, device_type)
        failed = self.get_failed_tests(device_id)
        return supported, failed


# Global capability detector instance
detector = DeviceCapabilityDetector()


# Set-based capability detection functions for DeviceProfile integration
async def detect_capabilities_as_sets(client, device_id: str, device_type: DeviceType = DeviceType.NoUse) -> Tuple[Set[DeviceCapability], Set[DeviceCapability]]:
    """
    MAIN FUNCTION: Detect device capabilities and return as sets.
    
    This is the primary function for capability detection in the enhanced system.
    Returns (supported_capabilities, failed_capabilities) as sets for DeviceProfile.
    
    Args:
        client: MieleClient instance for testing capabilities
        device_id: The device identifier
        device_type: The device type for initial capability assumptions
        
    Returns:
        Tuple of (supported_capabilities, failed_capabilities) as sets
    """
    supported = set()
    failed = set()
    
    # Start with initial capabilities based on device type
    initial_caps = detector.get_initial_capabilities(device_type)
    
    # Test each capability
    for capability in DeviceCapability:
        if capability == DeviceCapability.NONE:
            continue
            
        try:
            # Test the capability using appropriate client method
            success = await _test_capability_function(client, device_id, capability)
            if success:
                supported.add(capability)
                detector.record_capability_test(device_id, capability, True)
            else:
                failed.add(capability)
                detector.record_capability_test(device_id, capability, False)
        except Exception as e:
            # Capability test failed
            failed.add(capability)
            detector.record_capability_test(device_id, capability, False)
            logger.debug(f"Capability test {capability.name} failed for device {device_id}: {e}")
    
    return supported, failed


async def _test_capability_function(client, device_id: str, capability: DeviceCapability) -> bool:
    """
    Test a specific capability on a device.
    
    Args:
        client: MieleClient instance
        device_id: The device identifier
        capability: The capability to test
        
    Returns:
        True if the capability is supported, False otherwise
    """
    try:
        if capability == DeviceCapability.STATE_REPORTING:
            await client.get_device_state(device_id)
            return True
        elif capability == DeviceCapability.PROGRAM_REPORTING:
            await client.get_device(device_id)
            return True
        elif capability == DeviceCapability.WAKE_UP:
            await client.wake_up(device_id)
            return True
        elif capability == DeviceCapability.REMOTE_START:
            return await client.can_remote_start(device_id)
        elif capability == DeviceCapability.PROGRAM_CATALOG:
            catalog = await client.get_program_catalog(device_id)
            return catalog is not None and len(catalog.get("programs", {})) > 0
        elif capability == DeviceCapability.DOP2_BASIC:
            # Test basic DOP2 access
            await client.get_device(device_id)
            return True
        else:
            # For unknown capabilities, assume they don't work
            return False
    except Exception:
        return False


def test_capability(capability: DeviceCapability):
    """
    Decorator for methods that test a specific capability.
    
    This decorator wraps a method to record whether a capability test succeeded or failed.
    Enhanced for Set-based capability tracking and DeviceProfile integration.
    
    Args:
        capability: The capability being tested
        
    Returns:
        Decorated function
    """
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            # Extract device_id from arguments
            device_id = None
            if hasattr(self, 'device_profile') and self.device_profile:
                device_id = self.device_profile.device_id
            elif len(args) > 0 and isinstance(args[0], str):
                device_id = args[0]
            
            try:
                result = await func(self, *args, **kwargs)
                # Record successful test
                if device_id:
                    detector.record_capability_test(device_id, capability, True)
                return result
            except Exception as e:
                # Record failed test
                if device_id:
                    detector.record_capability_test(device_id, capability, False)
                # Re-raise the exception
                raise
        return wrapper
    return decorator 