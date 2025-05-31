"""
Enhanced validation and safety features for Miele device commands.

Phase 4.2 - Research-backed validation with device compatibility matrix.
"""

import logging
from functools import wraps
from typing import Dict, Any, List, Set, Callable, Awaitable, Optional
from datetime import datetime

from asyncmiele.enums import DeviceType
from asyncmiele.exceptions.config import UnsupportedCapabilityError
from asyncmiele.exceptions.api import DeviceNotFoundError

logger = logging.getLogger(__name__)


# Phase 4.2 - Enhanced Exception Classes
class InvalidStateTransitionError(Exception):
    """Exception raised when device is not in required state for command."""
    
    def __init__(self, current_state: str, required_states: List[str], command: str):
        self.current_state = current_state
        self.required_states = required_states
        self.command = command
        super().__init__(
            f"Command '{command}' requires device in {required_states}, currently {current_state}"
        )


class ProcessActionError(Exception):
    """Exception for ProcessAction command failures."""
    
    def __init__(self, action: int, device_type: str, reason: str):
        self.action = action
        self.device_type = device_type
        self.reason = reason
        super().__init__(f"ProcessAction {action} failed on {device_type}: {reason}")


class DeviceActionError(Exception):
    """Exception for DeviceAction command failures."""
    
    def __init__(self, action: int, device_type: str, reason: str):
        self.action = action
        self.device_type = device_type
        self.reason = reason
        super().__init__(f"DeviceAction {action} failed on {device_type}: {reason}")


class UserRequestError(Exception):
    """Exception for UserRequest command failures."""
    
    def __init__(self, request: int, device_type: str, reason: str):
        self.request = request
        self.device_type = device_type
        self.reason = reason
        super().__init__(f"UserRequest {request} failed on {device_type}: {reason}")


class StandbyStateError(Exception):
    """Exception for standby state transition issues."""
    
    def __init__(self, current_state: int, required_state: str, command: str):
        self.current_state = current_state
        self.required_state = required_state
        self.command = command
        super().__init__(
            f"Command '{command}' requires {required_state}, device in StandbyState {current_state}"
        )


# Phase 4.3 - Complete Device Compatibility Matrix (Research-Based)
DEVICE_COMPATIBILITY_DETAILED = {
    DeviceType.OVEN: {
        "ProcessAction": {
            1: {"name": "start", "requirements": "remote_enabled"},
            2: {"name": "stop", "requirements": "program_running"}
        },
        "DeviceAction": {
            1: {"name": "power_on", "requirements": "mains_power"},
            2: {"name": "wake_up", "requirements": "network_standby"}
        },
        "UserRequest": {
            12141: {"name": "light_on", "requirements": "device_on"},
            12142: {"name": "light_off", "requirements": "device_on"}
        },
        "limitations": [
            "No remote pause - opening door pauses",
            "Requires remote enable before start",
            "Auto-off after programs complete"
        ],
        "power_states": ["Active", "NetworkIdle", "DeepSleep"],
        "standby_behavior": "Auto-sleep after idle period"
    },
    DeviceType.WASHING_MACHINE: {
        "ProcessAction": {
            1: {"name": "start", "requirements": "remote_start_mode"},
            2: {"name": "stop", "requirements": "program_running"},
            3: {"name": "pause", "requirements": "early_cycle_phase"}
        },
        "DeviceAction": {
            2: {"name": "wake_up", "requirements": "network_standby"}
        },
        "UserRequest": {
            2: {"name": "mute_buzzer", "requirements": "signal_active"},
            3: {"name": "extra_rinse", "requirements": "program_selected"},
            4: {"name": "enable_child_lock", "requirements": "device_on"},
            5: {"name": "disable_child_lock", "requirements": "device_on"}
        },
        "limitations": [
            "Cannot power on remotely - manual remote start required",
            "Pause only during add-load window (early in cycle)",
            "Auto-sleep after 30 minutes in remote start mode",
            "Cannot start if door not properly closed"
        ],
        "power_states": ["NetworkIdle", "DeepSleep"],
        "standby_behavior": "Deep sleep after 30 min timeout"
    },
    DeviceType.DRYER: {
        "ProcessAction": {
            1: {"name": "start", "requirements": "remote_start_mode"},
            2: {"name": "stop", "requirements": "program_running"},
            3: {"name": "pause", "requirements": "early_cycle_phase"}
        },
        "DeviceAction": {
            2: {"name": "wake_up", "requirements": "network_standby"}
        },
        "UserRequest": {
            2: {"name": "mute_buzzer", "requirements": "signal_active"},
            4: {"name": "enable_child_lock", "requirements": "device_on"},
            5: {"name": "disable_child_lock", "requirements": "device_on"}
        },
        "limitations": [
            "Cannot power on remotely",
            "Pause only in first 10 minutes",
            "Auto-sleep after 30 minutes in remote start mode"
        ],
        "power_states": ["NetworkIdle", "DeepSleep"],
        "standby_behavior": "Deep sleep after 30 min timeout"
    },
    DeviceType.DISHWASHER: {
        "ProcessAction": {
            1: {"name": "start", "requirements": "remote_start_mode"},
            2: {"name": "stop", "requirements": "program_running"}
        },
        "DeviceAction": {
            2: {"name": "wake_up", "requirements": "network_standby"}
        },
        "UserRequest": {
            2: {"name": "mute_buzzer", "requirements": "signal_active"},
            12141: {"name": "light_on", "requirements": "device_on"},
            12142: {"name": "light_off", "requirements": "device_on"}
        },
        "limitations": [
            "Cannot power on remotely",
            "No pause capability",
            "Auto-sleep after idle period"
        ],
        "power_states": ["NetworkIdle", "DeepSleep"],
        "standby_behavior": "Network idle, deep sleep after timeout"
    },
    DeviceType.COFFEE_MAKER: {
        "ProcessAction": {
            1: {"name": "start_program", "requirements": "device_ready"},
            2: {"name": "stop_program", "requirements": "program_running"}
        },
        "DeviceAction": {
            1: {"name": "power_on", "requirements": "mains_power"},
            2: {"name": "wake_up", "requirements": "network_standby"}
        },
        "UserRequest": {
            12143: {"name": "brew_espresso_single", "requirements": "device_ready"},
            12144: {"name": "brew_espresso_double", "requirements": "device_ready"},
            12145: {"name": "brew_coffee", "requirements": "device_ready"},
            12146: {"name": "brew_cappuccino", "requirements": "device_ready"},
            12147: {"name": "brew_latte_macchiato", "requirements": "device_ready"},
            12148: {"name": "brew_hot_water", "requirements": "device_ready"},
            12149: {"name": "rinse_system", "requirements": "device_on"},
            12150: {"name": "clean_milk_system", "requirements": "device_on"},
            12151: {"name": "descale_system", "requirements": "device_on"}
        },
        "limitations": [
            "Requires water tank filled",
            "Requires beans for coffee drinks",
            "Auto-sleep after 5 minutes idle"
        ],
        "power_states": ["Active", "NetworkIdle", "DeepSleep"],
        "standby_behavior": "Auto-sleep after 5 min timeout"
    },
    DeviceType.FRIDGE: {
        "ProcessAction": {
            4: {"name": "start_superfreezing", "requirements": "device_on"},
            5: {"name": "stop_superfreezing", "requirements": "superfreezing_active"},
            6: {"name": "start_supercooling", "requirements": "device_on"},
            7: {"name": "stop_supercooling", "requirements": "supercooling_active"}
        },
        "UserRequest": {
            12141: {"name": "light_on", "requirements": "device_on"},
            12142: {"name": "light_off", "requirements": "device_on"}
        },
        "limitations": [
            "No power control - always on",
            "Limited remote functionality",
            "Primarily monitoring device"
        ],
        "power_states": ["Active"],
        "standby_behavior": "Always active - no standby modes"
    },
    DeviceType.FREEZER: {
        "ProcessAction": {
            4: {"name": "start_superfreezing", "requirements": "device_on"},
            5: {"name": "stop_superfreezing", "requirements": "superfreezing_active"},
            6: {"name": "start_supercooling", "requirements": "device_on"},
            7: {"name": "stop_supercooling", "requirements": "supercooling_active"}
        },
        "UserRequest": {
            12141: {"name": "light_on", "requirements": "device_on"},
            12142: {"name": "light_off", "requirements": "device_on"}
        },
        "limitations": [
            "No power control - always on",
            "Limited remote functionality",
            "Primarily monitoring device"
        ],
        "power_states": ["Active"],
        "standby_behavior": "Always active - no standby modes"
    },
    DeviceType.HOOD: {
        "ProcessAction": {
            1: {"name": "start", "requirements": "remote_enabled"},
            2: {"name": "stop", "requirements": "program_running"}
        },
        "DeviceAction": {
            1: {"name": "power_on", "requirements": "mains_power"},
            2: {"name": "wake_up", "requirements": "network_standby"}
        },
        "UserRequest": {
            2: {"name": "mute_buzzer", "requirements": "signal_active"},
            4: {"name": "enable_child_lock", "requirements": "device_on"},
            5: {"name": "disable_child_lock", "requirements": "device_on"}
        },
        "limitations": [
            "Manual operation primarily",
            "Limited remote functionality",
            "Safety restrictions for remote operation"
        ],
        "power_states": ["Active", "NetworkIdle", "DeepSleep"],
        "standby_behavior": "Auto-sleep after idle period"
    }
}


def get_device_compatibility(device_type: DeviceType) -> Dict[str, Any]:
    """Get compatibility information for a device type.
    
    Args:
        device_type: The device type to get compatibility for
        
    Returns:
        Compatibility dictionary with supported commands and limitations
    """
    return DEVICE_COMPATIBILITY_DETAILED.get(device_type, {
        "ProcessAction": {},
        "DeviceAction": {},
        "UserRequest": {},
        "limitations": ["Unknown device type - limited functionality"],
        "power_states": ["Active"],
        "standby_behavior": "Unknown"
    })


def require_power_state(*states: str):
    """Decorator to ensure device is in required power state before executing command.
    
    Args:
        *states: Required power states (e.g., "Active", "NetworkIdle")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Get current power state (assuming appliance has get_power_state method)
            try:
                current_state = await self.get_power_state()
            except AttributeError:
                # If method doesn't exist, assume we can proceed
                logger.warning(f"Cannot check power state for {func.__name__} - proceeding")
                return await func(self, *args, **kwargs)
            
            if current_state not in states:
                raise InvalidStateTransitionError(current_state, list(states), func.__name__)
            
            return await func(self, *args, **kwargs)
        return wrapper
    return decorator


def require_device_compatibility(action_type: str, action_value: int):
    """Decorator to ensure device supports specific action before executing.
    
    Args:
        action_type: Type of action ("ProcessAction", "DeviceAction", "UserRequest")
        action_value: Numeric value of the action
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Get device type (assuming appliance has get_device_type method)
            try:
                if hasattr(self, '_client'):
                    # Appliance class
                    ident = await self._client.get_device_ident(self.id)
                    device_type = DeviceType(ident.device_type) if isinstance(ident.device_type, int) else getattr(DeviceType, ident.device_type, DeviceType.NoUse)
                else:
                    # MieleClient class
                    device_type = DeviceType.NoUse  # Fallback
            except Exception:
                # If we can't determine device type, proceed with warning
                logger.warning(f"Cannot determine device type for {func.__name__} - proceeding")
                return await func(self, *args, **kwargs)
            
            compatibility = get_device_compatibility(device_type)
            
            if action_value not in compatibility.get(action_type, {}):
                device_name = device_type.name if device_type != DeviceType.NoUse else "Unknown"
                raise UnsupportedCapabilityError(
                    f"Device {device_name} does not support {action_type} {action_value}"
                )
            
            return await func(self, *args, **kwargs)
        return wrapper
    return decorator


def log_command_execution(func: Callable) -> Callable:
    """Decorator to log command execution for monitoring and debugging.
    
    Args:
        func: Function to decorate
    """
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        command_type = func.__name__
        device_id = getattr(self, 'id', args[0] if args else 'unknown')
        
        start_time = datetime.utcnow()
        success = False
        error_message = None
        
        try:
            result = await func(self, *args, **kwargs)
            success = True
            return result
        except Exception as exc:
            error_message = str(exc)
            raise
        finally:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            log_entry = {
                "timestamp": start_time.isoformat(),
                "command": command_type,
                "device_id": device_id,
                "success": success,
                "execution_time_seconds": execution_time,
                "error": error_message,
                "args_count": len(args),
                "kwargs_keys": list(kwargs.keys()) if kwargs else []
            }
            
            if success:
                logger.info(f"Command executed successfully: {log_entry}")
            else:
                logger.error(f"Command failed: {log_entry}")
    
    return wrapper


async def validate_command(device_type: DeviceType, action_type: str, 
                          action_value: int, current_state: Dict[str, Any]) -> Dict[str, Any]:
    """Validate if a command is supported on a device and check requirements.
    
    Args:
        device_type: The type of device
        action_type: Type of action ("ProcessAction", "DeviceAction", "UserRequest")
        action_value: Numeric value of the action
        current_state: Current device state dictionary
        
    Returns:
        Validation result with support status and requirements
    """
    compatibility = get_device_compatibility(device_type)
    
    action_info = compatibility.get(action_type, {}).get(action_value)
    if not action_info:
        return {
            "supported": False,
            "reason": f"{action_type} {action_value} not supported on {device_type.name}"
        }
    
    # Check requirements based on research
    requirements = action_info.get("requirements", "")
    
    if requirements == "remote_enabled":
        remote_enable = current_state.get("RemoteEnable", [])
        if 15 not in remote_enable:  # Full remote control flag
            return {
                "supported": False,
                "reason": "Remote control not enabled on device"
            }
    
    elif requirements == "program_running":
        status = current_state.get("status", "")
        if status not in ["Running", "running", "Programmed", "programmed"]:
            return {
                "supported": False,
                "reason": "No program currently running"
            }
    
    elif requirements == "device_on":
        standby_state = current_state.get("StandbyState", 2)
        if standby_state == 2:  # Deep sleep
            return {
                "supported": False,
                "reason": "Device in deep sleep - wake up required"
            }
    
    elif requirements == "early_cycle_phase":
        phase = current_state.get("programPhase", "")
        elapsed_time = current_state.get("elapsedTime", [0, 0])
        elapsed_minutes = elapsed_time[0] * 60 + elapsed_time[1] if len(elapsed_time) >= 2 else 999
        
        if elapsed_minutes > 10:  # More than 10 minutes elapsed
            return {
                "supported": False,
                "reason": "Pause only available in first 10 minutes of cycle"
            }
    
    return {
        "supported": True,
        "info": action_info,
        "requirements_met": True
    }


def get_device_limitations(device_type: DeviceType) -> List[str]:
    """Get list of known limitations for a device type.
    
    Args:
        device_type: The device type
        
    Returns:
        List of limitation descriptions
    """
    compatibility = get_device_compatibility(device_type)
    return compatibility.get("limitations", [])


def get_supported_power_states(device_type: DeviceType) -> List[str]:
    """Get list of supported power states for a device type.
    
    Args:
        device_type: The device type
        
    Returns:
        List of supported power state names
    """
    compatibility = get_device_compatibility(device_type)
    return compatibility.get("power_states", ["Active"])


def get_standby_behavior(device_type: DeviceType) -> str:
    """Get description of standby behavior for a device type.
    
    Args:
        device_type: The device type
        
    Returns:
        Description of standby behavior
    """
    compatibility = get_device_compatibility(device_type)
    return compatibility.get("standby_behavior", "Unknown standby behavior") 