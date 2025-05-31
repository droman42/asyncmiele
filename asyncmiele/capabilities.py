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
    
    # Program control capabilities (Phase 1 additions)
    PROGRAM_STOP = auto()          # Device supports stopping programs
    PROGRAM_PAUSE = auto()         # Device supports pausing programs  
    PROGRAM_RESUME = auto()        # Device supports resuming programs
    PROGRAM_OPTION_MODIFY = auto() # Device supports modifying options
    
    # Advanced device capabilities (Phase 1 additions)
    SUPERFREEZING = auto()         # Device supports SuperFreeze function
    SUPERCOOLING = auto()          # Device supports SuperCool function
    GAS_CONTROL = auto()           # Device supports gas enable/disable
    
    # DOP2 capabilities
    DOP2_BASIC = auto()            # Device supports basic DOP2 access
    DOP2_ADVANCED = auto()         # Device supports advanced DOP2 features
    
    # Data capabilities
    CONSUMPTION_STATS = auto()     # Device provides consumption statistics
    
    # Power control capabilities (Phase 2 additions)
    POWER_CONTROL = auto()         # Device supports power off/standby
    LIGHT_CONTROL = auto()         # Device supports interior light control
    USER_REQUESTS = auto()         # Device supports UserRequest commands
    BUZZER_CONTROL = auto()        # Device supports buzzer mute
    CHILD_LOCK = auto()            # Device supports child lock toggle


# Predefined capability sets for different device types (converted to sets)
DEFAULT_CAPABILITIES = {
    DeviceType.WashingMachine: {
        DeviceCapability.STATE_REPORTING,
        DeviceCapability.PROGRAM_REPORTING,
        DeviceCapability.WAKE_UP,
        DeviceCapability.REMOTE_START,
        DeviceCapability.PROGRAM_CATALOG,
        DeviceCapability.DOP2_BASIC,
        # Phase 1 additions for washing machines
        DeviceCapability.PROGRAM_STOP,
        DeviceCapability.PROGRAM_PAUSE,
        DeviceCapability.PROGRAM_RESUME,
        # Phase 2 additions for washing machines
        DeviceCapability.BUZZER_CONTROL,
        DeviceCapability.CHILD_LOCK,
        DeviceCapability.USER_REQUESTS,
    },
    DeviceType.TumbleDryer: {
        DeviceCapability.STATE_REPORTING,
        DeviceCapability.PROGRAM_REPORTING,
        DeviceCapability.WAKE_UP,
        DeviceCapability.REMOTE_START,
        DeviceCapability.PROGRAM_CATALOG,
        DeviceCapability.DOP2_BASIC,
        # Phase 1 additions for dryers
        DeviceCapability.PROGRAM_STOP,
        DeviceCapability.PROGRAM_PAUSE,
        DeviceCapability.PROGRAM_RESUME,
        # Phase 2 additions for dryers
        DeviceCapability.BUZZER_CONTROL,
        DeviceCapability.USER_REQUESTS,
    },
    DeviceType.Dishwasher: {
        DeviceCapability.STATE_REPORTING,
        DeviceCapability.PROGRAM_REPORTING,
        DeviceCapability.WAKE_UP,
        DeviceCapability.REMOTE_START,
        DeviceCapability.PROGRAM_CATALOG,
        DeviceCapability.DOP2_BASIC,
        # Phase 1 additions for dishwashers
        DeviceCapability.PROGRAM_STOP,
        # Note: No PROGRAM_PAUSE for dishwashers per research
        # Phase 2 additions for dishwashers
        DeviceCapability.BUZZER_CONTROL,
        DeviceCapability.LIGHT_CONTROL,  # Some models
        DeviceCapability.USER_REQUESTS,
    },
    DeviceType.Oven: {
        DeviceCapability.STATE_REPORTING,
        DeviceCapability.PROGRAM_REPORTING,
        DeviceCapability.WAKE_UP,
        DeviceCapability.REMOTE_START,
        DeviceCapability.PROGRAM_CATALOG,
        DeviceCapability.DOP2_BASIC,
        # Phase 1 additions for ovens
        DeviceCapability.PROGRAM_STOP,
        # Note: No PROGRAM_PAUSE for ovens per research (door opening pauses)
        # Phase 2 additions for ovens
        DeviceCapability.POWER_CONTROL,
        DeviceCapability.LIGHT_CONTROL,
        DeviceCapability.USER_REQUESTS,
    },
    # Add capability mappings for other device types
    DeviceType.CoffeeMaker: {
        DeviceCapability.STATE_REPORTING,
        DeviceCapability.PROGRAM_REPORTING,
        DeviceCapability.WAKE_UP,
        DeviceCapability.REMOTE_START,
        DeviceCapability.PROGRAM_CATALOG,
        DeviceCapability.DOP2_BASIC,
        DeviceCapability.PROGRAM_STOP,
        # Phase 2 additions for coffee makers
        DeviceCapability.POWER_CONTROL,
        DeviceCapability.USER_REQUESTS,  # Extensive coffee functions
    },
    DeviceType.Hood: {
        DeviceCapability.STATE_REPORTING,
        DeviceCapability.PROGRAM_REPORTING,
        DeviceCapability.WAKE_UP,
        DeviceCapability.DOP2_BASIC,
        # Phase 2 additions for hood (limited power control for cooktop functionality)
        # Note: Limited power control - may not work reliably for cooktop mode
    },
    DeviceType.Fridge: {
        DeviceCapability.STATE_REPORTING,
        DeviceCapability.PROGRAM_REPORTING,
        DeviceCapability.DOP2_BASIC,
        DeviceCapability.SUPERFREEZING,
        DeviceCapability.SUPERCOOLING,
        # Phase 2 additions for fridge
        DeviceCapability.LIGHT_CONTROL,
        DeviceCapability.USER_REQUESTS,
    },
    DeviceType.Freezer: {
        DeviceCapability.STATE_REPORTING,
        DeviceCapability.PROGRAM_REPORTING,
        DeviceCapability.DOP2_BASIC,
        DeviceCapability.SUPERFREEZING,
    },
    DeviceType.WasherDryer: {
        DeviceCapability.STATE_REPORTING,
        DeviceCapability.PROGRAM_REPORTING,
        DeviceCapability.WAKE_UP,
        DeviceCapability.REMOTE_START,
        DeviceCapability.PROGRAM_CATALOG,
        DeviceCapability.DOP2_BASIC,
        DeviceCapability.PROGRAM_STOP,
        DeviceCapability.PROGRAM_PAUSE,
        DeviceCapability.PROGRAM_RESUME,
        # Phase 2 additions for washer dryer
        DeviceCapability.BUZZER_CONTROL,
        DeviceCapability.CHILD_LOCK,
        DeviceCapability.USER_REQUESTS,
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
            # Test basic DOP2 access - try to read system info leaf
            await client.read_dop2_leaf(device_id, 1, 2)
            return True
        elif capability == DeviceCapability.DOP2_ADVANCED:
            # Test advanced DOP2 access - try to read combined state leaf
            await client.read_dop2_leaf(device_id, 2, 1586)
            return True
        elif capability == DeviceCapability.CONSUMPTION_STATS:
            # Test consumption stats capability
            stats = await client.get_consumption_stats(device_id)
            return bool(stats)
        elif capability == DeviceCapability.REMOTE_CONTROL:
            # Test remote control capability
            await client.get_device_state(device_id)
            return True
        elif capability == DeviceCapability.PARAMETER_SELECTION:
            # Test parameter selection - try SF_VALUE leaf
            await client.read_dop2_leaf(device_id, 2, 105)
            return True
        elif capability == DeviceCapability.PROGRAM_SELECTION:
            # Test program selection capability
            await client.get_device(device_id)
            return True
        elif capability == DeviceCapability.PROGRAM_STOP:
            # Test program stop capability
            await client.stop_program(device_id)
            return True
        elif capability == DeviceCapability.PROGRAM_PAUSE:
            # Test program pause capability
            await client.pause_program(device_id)
            return True
        elif capability == DeviceCapability.PROGRAM_RESUME:
            # Test program resume capability
            await client.resume_program(device_id)
            return True
        elif capability == DeviceCapability.PROGRAM_OPTION_MODIFY:
            # Test program option modify capability - use correct method name
            await client.set_program_option(device_id, 1000, 1)  # Test with dummy values
            return True
        elif capability == DeviceCapability.SUPERFREEZING:
            # Test superfreezing capability - not implemented yet, return False for now
            return False
        elif capability == DeviceCapability.SUPERCOOLING:
            # Test supercooling capability - not implemented yet, return False for now
            return False
        elif capability == DeviceCapability.GAS_CONTROL:
            # Test gas control capability - not implemented yet, return False for now
            return False
        elif capability == DeviceCapability.POWER_CONTROL:
            # Test power control capability - not implemented yet, return False for now
            return False
        elif capability == DeviceCapability.LIGHT_CONTROL:
            # Test light control capability - not implemented yet, return False for now
            return False
        elif capability == DeviceCapability.USER_REQUESTS:
            # Test user requests capability - not implemented yet, return False for now
            return False
        elif capability == DeviceCapability.BUZZER_CONTROL:
            # Test buzzer control capability - not implemented yet, return False for now
            return False
        elif capability == DeviceCapability.CHILD_LOCK:
            # Test child lock capability - not implemented yet, return False for now
            return False
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