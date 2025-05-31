"""
Device compatibility matrix for Miele devices.

This module contains detailed mappings of which commands each device type supports,
based on research findings from the Miele protocol analysis.
"""

from typing import Dict, Any, List
from asyncmiele.enums import DeviceType


# Device compatibility matrix based on research findings
DEVICE_COMPATIBILITY = {
    DeviceType.OVEN: {
        "ProcessAction": [1, 2],        # Start, Stop only (no pause)
        "DeviceAction": [1, 2],         # Power on/off supported
        "UserRequest": [12141, 12142],  # Light control
        "limitations": ["No remote pause - opening door pauses"]
    },
    # Note: Using HOOD for cooktop since COOKTOP doesn't exist in enum
    DeviceType.HOOD: {
        "ProcessAction": [1],           # Start only (very limited) - limited for cooktops
        "DeviceAction": [2],            # Wake up only (power off limited)
        "UserRequest": [2, 3],          # Run-on timer, filter reset
        "limitations": [
            "Very limited remote control capabilities for cooktop functionality",
            "May not support all DeviceAction commands",
            "Power off may require manual confirmation",
            "Fan control via ventilationStep, not ProcessAction"
        ]
    },
    DeviceType.WASHING_MACHINE: {
        "ProcessAction": [1, 2, 3],     # Start, Stop, Pause
        "DeviceAction": [2],            # Wake up only (no remote power on)
        "UserRequest": [2, 3, 4],       # Buzzer mute, extra options
        "limitations": [
            "Pause only available early in cycle (add-load window)",
            "Cannot power on remotely - must be in remote-start mode",
            "Auto-sleep after 30 minutes"
        ]
    },
    DeviceType.DRYER: {
        "ProcessAction": [1, 2, 3],     # Start, Stop, Pause
        "DeviceAction": [2],            # Wake up only
        "UserRequest": [2, 3],          # Buzzer, anti-crease
        "limitations": ["Similar to washing machine"]
    },
    DeviceType.DISHWASHER: {
        "ProcessAction": [1, 2],        # Start, Stop (no pause)
        "DeviceAction": [2],            # Wake up only
        "UserRequest": [2, 12141, 12142], # Buzzer, light (some models)
        "limitations": ["Generally no remote pause capability"]
    },
    DeviceType.FRIDGE: {
        "ProcessAction": [4, 5, 6, 7],  # SuperFreeze/SuperCool only
        "DeviceAction": [],             # Always on (no power control)
        "UserRequest": [12141, 12142],  # Interior light
        "limitations": ["No cycle start/stop - always running"]
    },
    DeviceType.FREEZER: {
        "ProcessAction": [4, 5],        # SuperFreeze only
        "DeviceAction": [],             # Always on
        "UserRequest": [],              # Limited functions
        "limitations": ["No cycle start/stop - always running"]
    },
    DeviceType.COFFEE_MAKER: {
        "ProcessAction": [1, 2],        # Start brew, Stop
        "DeviceAction": [1, 2],         # Power on/off supported
        "UserRequest": list(range(12143, 12180)), # Many drink options
        "limitations": ["Drink selection via UserRequest codes"]
    },
    DeviceType.WASHER_DRYER: {
        "ProcessAction": [1, 2, 3],     # Start, Stop, Pause
        "DeviceAction": [2],            # Wake up only
        "UserRequest": [2, 3],          # Buzzer, anti-crease
        "limitations": ["Similar to washing machine and dryer combined"]
    }
}


def get_device_capabilities(device_type: DeviceType) -> Dict[str, Any]:
    """
    Get compatibility info for device type.
    
    Args:
        device_type: The type of device to get capabilities for
        
    Returns:
        Dictionary containing supported command lists and limitations
    """
    return DEVICE_COMPATIBILITY.get(device_type, {
        "ProcessAction": [],
        "DeviceAction": [],
        "UserRequest": [],
        "limitations": ["Unknown device type - capabilities not mapped"]
    })


def supports_process_action(device_type: DeviceType, action: int) -> bool:
    """
    Check if a device type supports a specific ProcessAction.
    
    Args:
        device_type: The type of device
        action: The ProcessAction value to check
        
    Returns:
        True if the device type supports the action
    """
    compatibility = get_device_capabilities(device_type)
    return action in compatibility.get("ProcessAction", [])


def supports_device_action(device_type: DeviceType, action: int) -> bool:
    """
    Check if a device type supports a specific DeviceAction.
    
    Args:
        device_type: The type of device
        action: The DeviceAction value to check
        
    Returns:
        True if the device type supports the action
    """
    compatibility = get_device_capabilities(device_type)
    return action in compatibility.get("DeviceAction", [])


def supports_user_request(device_type: DeviceType, request: int) -> bool:
    """
    Check if a device type supports a specific UserRequest.
    
    Args:
        device_type: The type of device
        request: The UserRequest value to check
        
    Returns:
        True if the device type supports the request
    """
    compatibility = get_device_capabilities(device_type)
    return request in compatibility.get("UserRequest", [])


def get_device_limitations(device_type: DeviceType) -> List[str]:
    """
    Get the known limitations for a device type.
    
    Args:
        device_type: The type of device
        
    Returns:
        List of limitation descriptions
    """
    compatibility = get_device_capabilities(device_type)
    return compatibility.get("limitations", []) 