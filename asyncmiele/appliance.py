"""High-level appliance proxy introduced in Phase-3.

Provides a device-centric façade wrapping around :class:`asyncmiele.api.client.MieleClient`.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, TypedDict, Callable, Awaitable, Set, Union, cast, Iterator, TypeVar, Generic
from datetime import datetime, timedelta

from asyncmiele.api.client import MieleClient
from asyncmiele.models.summary import DeviceSummary
from asyncmiele.programs import ProgramCatalog, build_dop2_selection
from asyncmiele.capabilities import DeviceCapability, detector
from asyncmiele.exceptions.config import UnsupportedCapabilityError
from asyncmiele.exceptions.api import DeviceNotFoundError
from asyncmiele.models.device_profile import DeviceProfile
from asyncmiele.config.loader import load_device_profile

__all__: Iterable[str] = ["Appliance", "ApplianceError", "ProgramError", "ApplianceConnectionError", 
                         "Credentials", "SimulationMode"]

# Define TypeVar for generic operations
T = TypeVar('T')

# Configure module logger
logger = logging.getLogger(__name__)


class ApplianceError(Exception):
    """Base exception for all appliance-related errors."""
    
    pass


class ProgramError(ApplianceError):
    """Exception raised for errors related to program operations."""
    
    pass


class ApplianceConnectionError(ApplianceError):
    """Exception raised for connection-related errors."""
    
    pass


class ProgramOption(TypedDict):
    """Type definition for program options."""
    
    id: int
    value: int


@dataclass
class Credentials:
    """Authentication credentials for Miele API."""
    
    username: str
    password: str
    client_id: Optional[str] = None
    client_secret: Optional[str] = None


class SimulationMode:
    """Constants for simulation modes."""
    
    DISABLED = "disabled"
    NORMAL = "normal"
    FAILURE = "failure"


# Type aliases for callback functions
StateCallback = Callable[[Dict[str, Any]], Awaitable[None]]
ProgramFinishedCallback = Callable[[], Awaitable[None]]


class Appliance:
    """Proxy bound to a single device ID for concise interactions."""

    def __init__(self, client: MieleClient, device_id: str, *, 
                 simulation_mode: str = SimulationMode.DISABLED,
                 custom_catalog: Dict[str, Any] = None,
                 device_profile: Optional[DeviceProfile] = None) -> None:  # noqa: D401
        """Initialize an appliance proxy for a specific device.
        
        Parameters
        ----------
        client : MieleClient
            The Miele API client to use for communication
        device_id : str
            The unique identifier of the device to control
        simulation_mode : str, optional
            Simulation mode for testing (default: disabled)
        custom_catalog : Dict[str, Any], optional
            Custom program catalog dictionary to use instead of loading from files
        device_profile : DeviceProfile, optional
            Device profile containing configuration and capability information
        """
        self._client = client
        self.id = device_id
        self._connected = True  # Assume initially connected
        self._simulation_mode = simulation_mode
        self._custom_catalog = custom_catalog
        self._device_profile = device_profile
        
        # Device capabilities and info cache
        self._capabilities: Optional[Dict[str, Any]] = None
        self._settings: Optional[Dict[str, Any]] = None
        self._connection_details: Optional[Dict[str, Any]] = None
        self._detected_capabilities: Optional[DeviceCapability] = None
        
        # Cache management
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: Dict[str, float] = {}
        self._default_ttl = 10.0  # Default 10 seconds TTL
        
        # State change notification
        self._state_callbacks: Set[StateCallback] = set()
        self._program_finished_callbacks: Set[ProgramFinishedCallback] = set()
        self._monitoring_task: Optional[asyncio.Task] = None
        self._monitoring_interval = 5.0  # Default 5 seconds polling interval
        self._last_program_state: Optional[str] = None
        
        # Retry configuration
        self._max_retries = 3
        self._retry_delay = 1.0  # seconds

    # ------------------------------------------------------------------
    # Cache management

    def _get_cached(self, key: str) -> Optional[Any]:
        """Get a value from the cache if it exists and is not expired.
        
        Parameters
        ----------
        key : str
            Cache key
            
        Returns
        -------
        Any or None
            Cached value or None if not in cache or expired
        """
        if key not in self._cache:
            return None
            
        # Check if expired
        if key in self._cache_ttl and time.time() > self._cache_ttl[key]:
            del self._cache[key]
            del self._cache_ttl[key]
            return None
            
        return self._cache[key]
        
    def _set_cached(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set a value in the cache with optional TTL.
        
        Parameters
        ----------
        key : str
            Cache key
        value : Any
            Value to cache
        ttl : float, optional
            Time-to-live in seconds, default is self._default_ttl
        """
        self._cache[key] = value
        self._cache_ttl[key] = time.time() + (ttl or self._default_ttl)
        
    def _invalidate_cache(self, key: Optional[str] = None) -> None:
        """Invalidate cache entries.
        
        Parameters
        ----------
        key : str, optional
            Specific key to invalidate, or None to invalidate all
        """
        if key is None:
            self._cache.clear()
            self._cache_ttl.clear()
        elif key in self._cache:
            del self._cache[key]
            if key in self._cache_ttl:
                del self._cache_ttl[key]

    # ------------------------------------------------------------------
    # State monitoring

    async def _state_monitor_loop(self) -> None:
        """Background task to monitor state changes and trigger callbacks."""
        while self._connected:
            try:
                # Get current state
                current_state = await self.get_state()
                
                # Check for program finished
                current_program_state = current_state.get("programPhase")
                if (self._last_program_state is not None and 
                    self._last_program_state != "Finished" and 
                    current_program_state == "Finished"):
                    # Program just finished
                    for callback in self._program_finished_callbacks:
                        await callback()
                        
                self._last_program_state = current_program_state
                
                # Trigger state callbacks
                for callback in self._state_callbacks:
                    await callback(current_state)
                    
                await asyncio.sleep(self._monitoring_interval)
            except Exception as exc:
                # Don't let exceptions in the monitoring loop crash the task
                logger.error(f"Error in state monitoring: {exc}")
                await asyncio.sleep(self._monitoring_interval * 2)  # Back off on errors
    
    def _ensure_monitoring(self) -> None:
        """Ensure the state monitoring task is running."""
        if self._monitoring_task is None or self._monitoring_task.done():
            self._monitoring_task = asyncio.create_task(self._state_monitor_loop())
            
    def _stop_monitoring(self) -> None:
        """Stop the state monitoring task."""
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            self._monitoring_task = None

    # ------------------------------------------------------------------
    # Delegating helpers

    async def wake_up(self) -> None:
        """Wake a sleeping appliance."""
        if self._simulation_mode != SimulationMode.DISABLED:
            sim_result = self._simulate_response("wake_up")
            if sim_result is not None:
                return
                
        try:
            # Check capability first
            if self._device_profile:
                if not self._device_profile.has_capability(DeviceCapability.WAKE_UP):
                    logger.warning(f"Device {self.id} does not support wake_up")
                    return
            
            await self._with_retry(lambda: self._client.wake_up(self.id))
        except UnsupportedCapabilityError:
            logger.warning(f"Device {self.id} does not support wake_up")
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to wake up appliance: {exc}") from exc

    async def remote_start(self, *, allow_remote_start: Optional[bool] = None) -> None:
        """Start the currently prepared program.
        
        Parameters
        ----------
        allow_remote_start : bool, optional
            If True, ensure remote start is enabled before starting
        
        Raises
        ------
        ApplianceConnectionError
            If communication with the appliance fails
        ProgramError
            If the program cannot be started
        """
        if self._simulation_mode != SimulationMode.DISABLED:
            sim_result = self._simulate_response("remote_start")
            if sim_result is not None:
                return
        
        try:
            # Check capability first
            if self._device_profile:
                if not self._device_profile.has_capability(DeviceCapability.REMOTE_START):
                    raise UnsupportedCapabilityError(f"Device {self.id} does not support remote_start")
            
            await self._with_retry(lambda: self._client.remote_start(
                self.id, allow_remote_start=allow_remote_start
            ))
            
            # Invalidate cache for state
            self._invalidate_cache("state")
            self._invalidate_cache("can_remote_start")
        except UnsupportedCapabilityError:
            raise ProgramError(f"Remote start not supported by device {self.id}")
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to remote start: {exc}") from exc

    async def set_setting(self, sf_id: int, value: int) -> None:
        """Write a *Simple Feature* value via leaf 2/105.
        
        Parameters
        ----------
        sf_id : int
            Feature identifier
        value : int
            Value to set
            
        Raises
        ------
        ApplianceConnectionError
            If communication with the appliance fails
        """
        if self._simulation_mode != SimulationMode.DISABLED:
            sim_result = self._simulate_response("set_setting")
            if sim_result is not None:
                self._invalidate_cache()
                return
                
        try:
            await self._with_retry(lambda: self._client.set_setting(self.id, sf_id, value))
            # Invalidate cache after setting change
            self._invalidate_cache()
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to set setting: {exc}") from exc

    async def start_program(self, program_name: str, options: Optional[Dict[int, int]] = None) -> None:
        """Start a program with the given options.
        
        Parameters
        ----------
        program_name : str
            Name of the program to start
        options : Dict[int, int], optional
            Dictionary mapping option IDs to values
            
        Raises
        ------
        ProgramError
            If the program cannot be started
        ApplianceConnectionError
            If communication with the appliance fails
        """
        if self._simulation_mode != SimulationMode.DISABLED:
            sim_result = self._simulate_response("start_program")
            if sim_result is not None:
                return
        
        # Check capabilities first
        await self._check_program_capabilities()
                
        try:
            # Find the program by name
            programs = await self.get_available_programs()
            program = None
            
            for p in programs:
                if p.get("name") == program_name:
                    program = p
                    break
                    
            if program is None:
                raise ProgramError(f"Program '{program_name}' not found")
                
            # Build the selection command
            program_id = program["id"]
            
            # Get available options for this program
            program_options = await self.get_program_options(program_name)
            
            # Create selection structure
            selection = build_dop2_selection(program_id, options or {})
            
            # Wake up device first if needed
            if await self.has_capability(DeviceCapability.WAKE_UP):
                try:
                    await self.wake_up()
                    # Wait a bit after wake-up
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.warning(f"Wake-up failed but continuing: {e}")
            
            # Check if we need to enable remote start
            if await self.has_capability(DeviceCapability.REMOTE_START):
                try:
                    can_start = await self.can_remote_start()
                    if not can_start:
                        await self.remote_start(allow_remote_start=True)
                        # Wait a bit after enabling remote start
                        await asyncio.sleep(1)
                except Exception as e:
                    logger.warning(f"Remote start enable failed but continuing: {e}")
            
            # Send the selection
            await self._client.dop2_write_leaf(self.id, 14, 1536, selection)
            
            # Start the program
            await self.remote_start()
            
            # Invalidate cached state
            self._invalidate_cache("state")
            
        except Exception as exc:
            raise ProgramError(f"Failed to start program '{program_name}': {exc}") from exc

    async def _check_program_capabilities(self) -> None:
        """Check if the device supports program selection and raise an error if not.
        
        Uses Set-based capability operations for efficient checking.
        
        Raises
        ------
        ProgramError
            If the device does not support program operations
        UnsupportedCapabilityError
            If required capabilities are missing
        """
        # Define required capabilities as a set
        required_caps = {DeviceCapability.PROGRAM_CATALOG, DeviceCapability.PROGRAM_SELECTION}
        
        # Check if device profile has all required capabilities
        if self._device_profile:
            missing = self._device_profile.get_missing_capabilities(required_caps)
            if missing:
                raise UnsupportedCapabilityError(
                    f"Device {self.id} missing program capabilities: {[cap.name for cap in missing]}"
                )
            return
        
        # Fallback to individual capability checking
        missing_capabilities = []
        for capability in required_caps:
            if not await self.has_capability(capability):
                missing_capabilities.append(capability.name)
        
        if missing_capabilities:
            raise ProgramError(
                f"Device {self.id} does not support program operations. "
                f"Missing capabilities: {', '.join(missing_capabilities)}"
            )

    # ------------------------------------------------------------------
    # Basic functionality from Phase 1

    async def get_state(self) -> Dict[str, Any]:
        """Return the current state of the appliance.
        
        Returns
        -------
        Dict[str, Any]
            Complete state information including operation mode, progress, and status
            
        Raises
        ------
        ApplianceConnectionError
            If communication with the appliance fails
        """
        # Check cache first
        cached_state = self._get_cached("state")
        if cached_state is not None:
            return cached_state
        
        # Handle simulation mode
        if self._simulation_mode != SimulationMode.DISABLED:
            sim_result = self._simulate_response("get_state")
            if sim_result is not None:
                self._set_cached("state", sim_result)
                return sim_result
            
        try:
            summary = await self._with_retry(lambda: self.summary())
            state = summary.state.model_dump() if summary.state else {}
            
            # Enhance with additional state information
            if summary.status:
                state.update(summary.status.model_dump())
                
            # Cache the result
            self._set_cached("state", state)
            return state
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to get appliance state: {exc}") from exc

    async def get_error_status(self) -> Dict[str, Any]:
        """Return error information for the appliance.
        
        Returns
        -------
        Dict[str, Any]
            Error codes and descriptions if any errors are present
            
        Raises
        ------
        ApplianceConnectionError
            If communication with the appliance fails
        """
        # Check cache first
        cached_errors = self._get_cached("errors")
        if cached_errors is not None:
            return cached_errors
            
        try:
            summary = await self.summary()
            if not summary.status:
                return {}
                
            error_info = {}
            if hasattr(summary.status, "error") and summary.status.error:
                error_info["error"] = summary.status.error
                
            if hasattr(summary.status, "error_description") and summary.status.error_description:
                error_info["error_description"] = summary.status.error_description
                
            # Cache with shorter TTL for errors (they're important)
            self._set_cached("errors", error_info, ttl=5.0)
            return error_info
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to get error status: {exc}") from exc

    async def stop_program(self) -> None:
        """Stop the currently running program.
        
        Raises
        ------
        ProgramError
            If stopping the program fails
        ApplianceConnectionError
            If communication with the appliance fails
        """
        try:
            # Assuming stop action is implemented in client
            await self._client.stop_program(self.id)
            # Invalidate cache after state change
            self._invalidate_cache()
        except Exception as exc:
            raise ProgramError(f"Failed to stop program: {exc}") from exc

    async def cancel_program(self) -> None:
        """Cancel the currently running program.
        
        Raises
        ------
        ProgramError
            If canceling the program fails
        ApplianceConnectionError
            If communication with the appliance fails
        """
        try:
            # Assuming cancel action is implemented in client
            await self._client.cancel_program(self.id)
            # Invalidate cache after state change
            self._invalidate_cache()
        except Exception as exc:
            raise ProgramError(f"Failed to cancel program: {exc}") from exc

    async def get_available_programs(self) -> List[Dict[str, Any]]:
        """Get a list of available programs for this appliance.
        
        Returns
        -------
        List[Dict[str, Any]]
            List of programs with their options
            
        Raises
        ------
        ApplianceConnectionError
            If communication with the appliance fails
        """
        # Check cache first
        cached_programs = self._get_cached("available_programs")
        if cached_programs is not None:
            return cached_programs
            
        # Check capabilities
        if not await self.has_capability(DeviceCapability.PROGRAM_CATALOG):
            logger.warning(f"Device {self.id} does not support program catalog")
            return []
        
        try:
            # Try to load from custom catalog if provided
            if self._custom_catalog is not None:
                programs = self._custom_catalog.get("programs", [])
                self._set_cached("available_programs", programs)
                return programs
                
            # Try to extract catalog from device
            try:
                catalog = await self._client.get_program_catalog(self.id)
                if catalog and "programs" in catalog:
                    programs = catalog["programs"]
                    self._set_cached("available_programs", programs)
                    return programs
            except UnsupportedCapabilityError:
                logger.warning(f"Device {self.id} does not support program catalog extraction")
                
            # If extraction failed, try to load from file based on device type
            ident = await self._client.get_device_ident(self.id)
            device_type = ident.type_id
                
            # Create catalog object which will load from resources
            catalog = ProgramCatalog.for_device_type(device_type)
            
            # Get programs from catalog
            programs = catalog.get_all_programs()
            
            # Cache the result
            self._set_cached("available_programs", programs)
            return programs
            
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to get available programs: {exc}") from exc

    async def get_program_options(self, program_name: str) -> List[Dict[str, Any]]:
        """Return available options for a specific program.
        
        Parameters
        ----------
        program_name : str
            Name of the program to get options for
            
        Returns
        -------
        List[Dict[str, Any]]
            Available options for the specified program
            
        Raises
        ------
        ValueError
            If the program name is unknown
        ApplianceConnectionError
            If communication with the appliance fails
        """
        # Check cache first
        cache_key = f"program_options_{program_name}"
        cached_options = self._get_cached(cache_key)
        if cached_options is not None:
            return cached_options
            
        try:
            # First try with custom catalog if available
            if self._custom_catalog:
                ident = await self._client.get_device_ident(self.id)
                catalog = ProgramCatalog.for_device(ident, custom_catalog=self._custom_catalog)
                
                try:
                    program = catalog.programs_by_name[program_name]
                except KeyError as exc:
                    raise ValueError(
                        f"Unknown program '{program_name}' for device type '{catalog.device_type}'"
                    ) from exc
                    
                # Extract option information from the static catalog
                options = []
                if hasattr(program, "options") and program.options:
                    for option in program.options:
                        options.append({
                            "id": option.id,
                            "name": option.name,
                            "values": option.allowed_values,
                            "default": option.default,
                        })
                
                # Cache with longer TTL
                self._set_cached(cache_key, options, ttl=60.0)
                return options
            
            # If no custom catalog, extract from device
            # First get all available programs to find the program ID
            programs = await self.get_available_programs()
            program_id = None
            
            for prog in programs:
                if prog["name"] == program_name:
                    program_id = prog["id"]
                    break
                    
            if program_id is None:
                raise ValueError(f"Unknown program '{program_name}'")
                
            # Get options for this program ID using leaf 2/105
            try:
                options_data = await self._client.dop2_get_parsed(self.id, 2, 105, idx1=program_id)
                options = []
                
                if isinstance(options_data, dict) and "options" in options_data:
                    for opt in options_data["options"]:
                        option = {
                            "id": opt.get("id"),
                            "name": opt.get("name", f"Option_{opt.get('id')}"),
                            "default": opt.get("default"),
                        }
                        if "allowed_values" in opt:
                            option["values"] = opt["allowed_values"]
                        options.append(option)
                
                # Cache with longer TTL
                self._set_cached(cache_key, options, ttl=60.0)
                return options
            except Exception:
                # If we can't get options from DOP2, return empty list
                self._set_cached(cache_key, [], ttl=60.0)
                return []
                
        except ValueError:
            raise
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to get program options: {exc}") from exc

    # ------------------------------------------------------------------
    # New Phase 2 control operations

    async def pause_program(self) -> None:
        """Pause the currently running program if supported.
        
        Raises
        ------
        ProgramError
            If pausing the program fails or is not supported
        ApplianceConnectionError
            If communication with the appliance fails
        """
        try:
            # Assuming pause action is implemented in client
            await self._client.pause_program(self.id)
            # Invalidate cache after state change
            self._invalidate_cache()
        except Exception as exc:
            raise ProgramError(f"Failed to pause program: {exc}") from exc

    async def resume_program(self) -> None:
        """Resume the paused program if supported.
        
        Raises
        ------
        ProgramError
            If resuming the program fails or is not supported
        ApplianceConnectionError
            If communication with the appliance fails
        """
        try:
            # Assuming resume action is implemented in client
            await self._client.resume_program(self.id)
            # Invalidate cache after state change
            self._invalidate_cache()
        except Exception as exc:
            raise ProgramError(f"Failed to resume program: {exc}") from exc

    async def set_program_option(self, option_id: int, value: int) -> None:
        """Set a specific program option while a program is running.
        
        Parameters
        ----------
        option_id : int
            ID of the option to set
        value : int
            Value to set
            
        Raises
        ------
        ProgramError
            If setting the option fails or is not supported
        ApplianceConnectionError
            If communication with the appliance fails
        """
        try:
            # Assuming this is implemented in client
            await self._client.set_program_option(self.id, option_id, value)
            # Invalidate cache after state change
            self._invalidate_cache()
        except Exception as exc:
            raise ProgramError(f"Failed to set program option: {exc}") from exc

    # ------------------------------------------------------------------
    # Phase 2 Power Control Methods

    async def power_on(self) -> None:
        """Power on the appliance.
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support power control
        ApplianceConnectionError
            If communication with the appliance fails
        """
        if not await self.has_capability(DeviceCapability.POWER_CONTROL):
            raise UnsupportedCapabilityError(f"Device {self.id} does not support power control")
        
        try:
            await self._client.power_on(self.id)
            self._invalidate_cache()
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to power on device: {exc}") from exc
    
    async def power_off(self) -> None:
        """Power off the appliance.
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support power control
        ApplianceConnectionError
            If communication with the appliance fails
        """
        if not await self.has_capability(DeviceCapability.POWER_CONTROL):
            raise UnsupportedCapabilityError(f"Device {self.id} does not support power control")
        
        try:
            await self._client.power_off(self.id)
            self._invalidate_cache()
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to power off device: {exc}") from exc
    
    async def standby(self) -> None:
        """Put appliance in standby mode (alias for power_off).
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support power control
        ApplianceConnectionError
            If communication with the appliance fails
        """
        await self.power_off()

    # ------------------------------------------------------------------
    # Phase 2 UserRequest Command Methods

    async def set_interior_light(self, on: bool) -> None:
        """Turn interior light on or off.
        
        Parameters
        ----------
        on : bool
            True to turn light on, False to turn off
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support light control
        ApplianceConnectionError
            If communication with the appliance fails
        """
        if not await self.has_capability(DeviceCapability.LIGHT_CONTROL):
            raise UnsupportedCapabilityError(f"Device {self.id} does not support light control")
        
        try:
            await self._client.set_interior_light(self.id, on)
            self._invalidate_cache()
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to control interior light: {exc}") from exc

    async def mute_buzzer(self) -> None:
        """Mute end-of-cycle buzzer.
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support buzzer control
        ApplianceConnectionError
            If communication with the appliance fails
        """
        if not await self.has_capability(DeviceCapability.BUZZER_CONTROL):
            raise UnsupportedCapabilityError(f"Device {self.id} does not support buzzer control")
        
        try:
            await self._client.mute_buzzer(self.id)
            self._invalidate_cache()
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to mute buzzer: {exc}") from exc

    async def toggle_child_lock(self, enable: bool) -> None:
        """Toggle child lock on device.
        
        Parameters
        ----------
        enable : bool
            True to enable child lock, False to disable
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support child lock
        ApplianceConnectionError
            If communication with the appliance fails
        """
        if not await self.has_capability(DeviceCapability.CHILD_LOCK):
            raise UnsupportedCapabilityError(f"Device {self.id} does not support child lock")
        
        try:
            await self._client.toggle_child_lock(self.id, enable)
            self._invalidate_cache()
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to toggle child lock: {exc}") from exc

    # ------------------------------------------------------------------
    # Phase 3.1 Enhanced UserRequest Methods

    async def brew_coffee(self, drink_type: str) -> None:
        """Brew specific coffee drink.
        
        Parameters
        ----------
        drink_type : str
            Type of drink to brew (e.g., 'espresso_single', 'cappuccino', 'latte_macchiato')
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support coffee functions
        ApplianceConnectionError
            If communication with the appliance fails
        ValueError
            If drink type is not supported
        """
        if not await self.has_capability(DeviceCapability.USER_REQUESTS):
            raise UnsupportedCapabilityError(f"Device {self.id} does not support coffee functions")
        
        try:
            await self._client.brew_coffee(self.id, drink_type)
            self._invalidate_cache()
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to brew {drink_type}: {exc}") from exc

    async def coffee_maintenance(self, action: str) -> None:
        """Perform coffee machine maintenance actions.
        
        Parameters
        ----------
        action : str
            Maintenance action ('rinse', 'clean', 'descale')
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support coffee maintenance
        ApplianceConnectionError
            If communication with the appliance fails
        ValueError
            If action is not supported
        """
        if not await self.has_capability(DeviceCapability.USER_REQUESTS):
            raise UnsupportedCapabilityError(f"Device {self.id} does not support coffee maintenance")
        
        try:
            await self._client.coffee_maintenance(self.id, action)
            self._invalidate_cache()
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to perform {action}: {exc}") from exc

    async def set_sabbath_mode(self, enable: bool) -> None:
        """Toggle Sabbath mode on compatible devices.
        
        Parameters
        ----------
        enable : bool
            True to enable Sabbath mode, False to disable
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support smart home modes
        ApplianceConnectionError
            If communication with the appliance fails
        """
        if not await self.has_capability(DeviceCapability.USER_REQUESTS):
            raise UnsupportedCapabilityError(f"Device {self.id} does not support smart home modes")
        
        try:
            await self._client.set_sabbath_mode(self.id, enable)
            self._invalidate_cache()
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to set Sabbath mode: {exc}") from exc

    async def set_demo_mode(self, enable: bool) -> None:
        """Toggle demo mode on compatible devices.
        
        Parameters
        ----------
        enable : bool
            True to enable demo mode, False to disable
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support demo mode
        ApplianceConnectionError
            If communication with the appliance fails
        """
        if not await self.has_capability(DeviceCapability.USER_REQUESTS):
            raise UnsupportedCapabilityError(f"Device {self.id} does not support demo mode")
        
        try:
            await self._client.set_demo_mode(self.id, enable)
            self._invalidate_cache()
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to set demo mode: {exc}") from exc

    async def signal_control(self, action: str) -> None:
        """Control device signals and sounds.
        
        Parameters
        ----------
        action : str
            Signal action ('mute', 'test_signal', 'end_signal')
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support signal control
        ApplianceConnectionError
            If communication with the appliance fails
        ValueError
            If action is not supported
        """
        if not await self.has_capability(DeviceCapability.USER_REQUESTS):
            raise UnsupportedCapabilityError(f"Device {self.id} does not support signal control")
        
        try:
            await self._client.signal_control(self.id, action)
            self._invalidate_cache()
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to control signal: {exc}") from exc

    async def door_control(self, action: str) -> None:
        """Control door lock functions.
        
        Parameters
        ----------
        action : str
            Door action ('lock', 'unlock')
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support door control
        ApplianceConnectionError
            If communication with the appliance fails
        ValueError
            If action is not supported
        """
        if not await self.has_capability(DeviceCapability.USER_REQUESTS):
            raise UnsupportedCapabilityError(f"Device {self.id} does not support door control")
        
        try:
            await self._client.door_control(self.id, action)
            self._invalidate_cache()
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to control door: {exc}") from exc

    async def timer_control(self, action: str) -> None:
        """Control timer functions.
        
        Parameters
        ----------
        action : str
            Timer action ('start_timer', 'stop_timer', 'reset_timer')
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support timer control
        ApplianceConnectionError
            If communication with the appliance fails
        ValueError
            If action is not supported
        """
        if not await self.has_capability(DeviceCapability.USER_REQUESTS):
            raise UnsupportedCapabilityError(f"Device {self.id} does not support timer control")
        
        try:
            await self._client.timer_control(self.id, action)
            self._invalidate_cache()
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to control timer: {exc}") from exc

    # ------------------------------------------------------------------
    # Phase 4.1 Refrigeration Control Methods

    async def start_superfreezing(self) -> None:
        """Start superfreezing mode on refrigeration devices.
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support superfreezing
        ApplianceConnectionError
            If communication with the appliance fails
        """
        if not await self.has_capability(DeviceCapability.SUPERFREEZING):
            raise UnsupportedCapabilityError(f"Device {self.id} does not support superfreezing")
        
        try:
            await self._client.start_superfreezing(self.id)
            self._invalidate_cache()
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to start superfreezing: {exc}") from exc

    async def stop_superfreezing(self) -> None:
        """Stop superfreezing mode on refrigeration devices.
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support superfreezing
        ApplianceConnectionError
            If communication with the appliance fails
        """
        if not await self.has_capability(DeviceCapability.SUPERFREEZING):
            raise UnsupportedCapabilityError(f"Device {self.id} does not support superfreezing")
        
        try:
            await self._client.stop_superfreezing(self.id)
            self._invalidate_cache()
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to stop superfreezing: {exc}") from exc

    async def start_supercooling(self) -> None:
        """Start supercooling mode on refrigeration devices.
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support supercooling
        ApplianceConnectionError
            If communication with the appliance fails
        """
        if not await self.has_capability(DeviceCapability.SUPERCOOLING):
            raise UnsupportedCapabilityError(f"Device {self.id} does not support supercooling")
        
        try:
            await self._client.start_supercooling(self.id)
            self._invalidate_cache()
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to start supercooling: {exc}") from exc

    async def stop_supercooling(self) -> None:
        """Stop supercooling mode on refrigeration devices.
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support supercooling
        ApplianceConnectionError
            If communication with the appliance fails
        """
        if not await self.has_capability(DeviceCapability.SUPERCOOLING):
            raise UnsupportedCapabilityError(f"Device {self.id} does not support supercooling")
        
        try:
            await self._client.stop_supercooling(self.id)
            self._invalidate_cache()
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to stop supercooling: {exc}") from exc

    # Convenience methods for coffee machine
    async def brew_espresso(self) -> None:
        """Brew single espresso (convenience method).
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support coffee functions
        ApplianceConnectionError
            If communication with the appliance fails
        """
        await self.brew_coffee("espresso_single")

    async def brew_cappuccino(self) -> None:
        """Brew cappuccino (convenience method).
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support coffee functions
        ApplianceConnectionError
            If communication with the appliance fails
        """
        await self.brew_coffee("cappuccino")

    async def rinse_system(self) -> None:
        """Rinse coffee system (convenience method).
        
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support coffee maintenance
        ApplianceConnectionError
            If communication with the appliance fails
        """
        await self.coffee_maintenance("rinse")

    # ------------------------------------------------------------------
    # Phase 3.2 DOP2 Tree Exploration Methods

    async def explore_device_structure(self) -> Dict[str, Any]:
        """Explore the complete device DOP2 structure.
        
        This method walks the entire DOP2 tree to discover all available
        units and attributes, providing comprehensive insight into device capabilities.
        
        Returns
        -------
        Dict[str, Any]
            Complete DOP2 tree structure as nested dictionary
            
        Raises
        ------
        ApplianceConnectionError
            If communication with the appliance fails
        """
        try:
            return await self._client.walk_dop2_tree(self.id)
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to explore device structure: {exc}") from exc

    async def explore_unit_leaves(self, unit: int) -> List[int]:
        """Explore available leaves in a specific DOP2 unit.
        
        Parameters
        ----------
        unit : int
            The DOP2 unit number to explore
            
        Returns
        -------
        List[int]
            List of available attribute numbers in the unit
            
        Raises
        ------
        ApplianceConnectionError
            If communication with the appliance fails
        """
        try:
            return await self._client.explore_dop2_leaves(self.id, unit)
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to explore unit {unit}: {exc}") from exc

    async def map_power_control_dop2(self) -> Dict[str, Any]:
        """Map DOP2 power control attributes for this device.
        
        Returns
        -------
        Dict[str, Any]
            Dictionary mapping potential power control paths to their data
            
        Raises
        ------
        ApplianceConnectionError
            If communication with the appliance fails
        """
        try:
            return await self._client.map_dop2_power_control(self.id)
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to map power control: {exc}") from exc

    # ------------------------------------------------------------------
    # Phase 3.3 Enhanced Device State Management

    async def ensure_awake(self) -> bool:
        """Ensure device is awake before sending commands.
        
        This method checks the device's standby state and wakes it up if necessary.
        Based on research-confirmed StandbyState mappings.
        
        Returns
        -------
        bool
            True if device is awake or was successfully woken up,
            False if device cannot be woken (needs manual intervention)
            
        Raises
        ------
        ApplianceConnectionError
            If communication with the appliance fails
        """
        try:
            state = await self.get_state()
            standby_state = state.get("StandbyState", 0)
            
            if standby_state == 2:  # Deep sleep - research confirmed
                if await self.has_capability(DeviceCapability.WAKE_UP):
                    await self.wake_up()
                    await asyncio.sleep(1)  # Wait for wake up
                    return True
                else:
                    return False  # Cannot wake - needs manual intervention
            return True  # Already awake
            
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to ensure device is awake: {exc}") from exc

    async def safe_power_off(self) -> bool:
        """Safely power off device (stop programs first if needed).
        
        This method ensures programs are stopped before powering off the device
        to prevent data loss or unsafe states.
        
        Returns
        -------
        bool
            True if device was safely powered off
            
        Raises
        ------
        UnsupportedCapabilityError
            If the device does not support power control
        ApplianceConnectionError
            If communication with the appliance fails
        """
        if not await self.has_capability(DeviceCapability.POWER_CONTROL):
            raise UnsupportedCapabilityError(f"Device {self.id} does not support power control")
            
        try:
            state = await self.get_state()
            
            # Check if a program is running and stop it first
            if state.get("status") in ["Running", "Programmed"]:
                if await self.has_capability(DeviceCapability.PROGRAM_STOP):
                    logger.info(f"Stopping running program before power off on device {self.id}")
                    await self.stop_program()
                    await asyncio.sleep(2)  # Wait for stop
                    
            # Now power off the device
            await self.power_off()
            return True
            
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to safely power off device: {exc}") from exc

    async def get_power_state(self) -> str:
        """Get current power state based on StandbyState.
        
        Based on research-confirmed StandbyState mappings from protocol analysis.
        
        Returns
        -------
        str
            Current power state: 'Active', 'NetworkIdle', 'DeepSleep', or 'Unknown'
            
        Raises
        ------
        ApplianceConnectionError
            If communication with the appliance fails
        """
        try:
            state = await self.get_state()
            standby_state = state.get("StandbyState", 0)
            
            # Research confirmed these mappings:
            if standby_state == 0:
                return "Active"  # Not in standby
            elif standby_state == 1:
                return "NetworkIdle"  # Can respond to commands
            elif standby_state == 2:
                return "DeepSleep"  # Effectively offline
            else:
                return "Unknown"
                
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to get power state: {exc}") from exc

    async def wait_for_power_state(self, target_state: str, timeout: float = 30.0) -> bool:
        """Wait for device to reach specific power state.
        
        Parameters
        ----------
        target_state : str
            Target power state ('Active', 'NetworkIdle', 'DeepSleep')
        timeout : float
            Maximum time to wait in seconds (default: 30.0)
            
        Returns
        -------
        bool
            True if target state was reached, False if timeout occurred
            
        Raises
        ------
        ApplianceConnectionError
            If communication with the appliance fails
        ValueError
            If target_state is not valid
        """
        valid_states = ["Active", "NetworkIdle", "DeepSleep", "Unknown"]
        if target_state not in valid_states:
            raise ValueError(f"Invalid target state '{target_state}'. Valid states: {valid_states}")
            
        try:
            start_time = time.time()
            while time.time() - start_time < timeout:
                current_state = await self.get_power_state()
                if current_state == target_state:
                    logger.info(f"Device {self.id} reached target power state: {target_state}")
                    return True
                    
                logger.debug(f"Device {self.id} current power state: {current_state}, waiting for: {target_state}")
                await asyncio.sleep(1)
                
            logger.warning(f"Device {self.id} did not reach target power state {target_state} within {timeout}s")
            return False
            
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to wait for power state: {exc}") from exc

    async def get_standby_behavior(self) -> Dict[str, Any]:
        """Get information about device standby behavior.
        
        Returns detailed information about how the device handles standby states,
        based on device type and current configuration.
        
        Returns
        -------
        Dict[str, Any]
            Standby behavior information including auto-sleep timeouts and wake capabilities
        """
        try:
            # Get device identification to determine behavior
            ident = await self._client.get_device_ident(self.id)
            device_type = getattr(ident, 'device_type', 'Unknown')
            
            # Get current state
            current_state = await self.get_power_state()
            
            # Device-specific standby behavior based on research
            behavior_map = {
                'WashingMachine': {
                    'auto_sleep_timeout': 1800,  # 30 minutes in remote start mode
                    'supported_states': ['NetworkIdle', 'DeepSleep'],
                    'wake_capability': True,
                    'auto_power_off': False
                },
                'Oven': {
                    'auto_sleep_timeout': 900,   # 15 minutes after idle
                    'supported_states': ['Active', 'NetworkIdle', 'DeepSleep'], 
                    'wake_capability': True,
                    'auto_power_off': True  # Auto-off after programs complete
                },
                'CoffeeMaker': {
                    'auto_sleep_timeout': 300,   # 5 minutes
                    'supported_states': ['Active', 'NetworkIdle', 'DeepSleep'],
                    'wake_capability': True,
                    'auto_power_off': False
                },
                'Dishwasher': {
                    'auto_sleep_timeout': 600,   # 10 minutes
                    'supported_states': ['NetworkIdle', 'DeepSleep'],
                    'wake_capability': True,
                    'auto_power_off': False
                }
            }
            
            default_behavior = {
                'auto_sleep_timeout': 600,  # Default 10 minutes
                'supported_states': ['Active', 'NetworkIdle'],
                'wake_capability': True,
                'auto_power_off': False
            }
            
            behavior = behavior_map.get(device_type, default_behavior)
            behavior['current_state'] = current_state
            behavior['device_type'] = device_type
            
            return behavior
            
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to get standby behavior: {exc}") from exc

    # ------------------------------------------------------------------
    # New Phase 2 notification methods

    async def register_state_callback(self, callback: StateCallback) -> None:
        """Register a callback to be called when the appliance state changes.
        
        Parameters
        ----------
        callback : Callable[[Dict[str, Any]], Awaitable[None]]
            Async function to call with the new state
        """
        self._state_callbacks.add(callback)
        self._ensure_monitoring()
        
    async def unregister_state_callback(self, callback: StateCallback) -> None:
        """Unregister a previously registered state callback.
        
        Parameters
        ----------
        callback : Callable[[Dict[str, Any]], Awaitable[None]]
            Previously registered callback
        """
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)
            
        # Stop monitoring if no callbacks remain
        if not self._state_callbacks and not self._program_finished_callbacks:
            self._stop_monitoring()
            
    async def register_program_finished_callback(self, callback: ProgramFinishedCallback) -> None:
        """Register a callback to be called when a program finishes.
        
        Parameters
        ----------
        callback : Callable[[], Awaitable[None]]
            Async function to call when program finishes
        """
        self._program_finished_callbacks.add(callback)
        self._ensure_monitoring()
        
    async def unregister_program_finished_callback(self, callback: ProgramFinishedCallback) -> None:
        """Unregister a previously registered program finished callback.
        
        Parameters
        ----------
        callback : Callable[[], Awaitable[None]]
            Previously registered callback
        """
        if callback in self._program_finished_callbacks:
            self._program_finished_callbacks.remove(callback)
            
        # Stop monitoring if no callbacks remain
        if not self._state_callbacks and not self._program_finished_callbacks:
            self._stop_monitoring()

    # ------------------------------------------------------------------
    # New Phase 2 connection management methods

    async def is_connected(self) -> bool:
        """Check if the appliance is connected and reachable.
        
        Returns
        -------
        bool
            True if connected and reachable
            
        Note
        ----
        This actually tests the connection by sending a request.
        """
        try:
            await self.summary()
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False
            
    async def disconnect(self) -> None:
        """Disconnect from the appliance.
        
        This stops all monitoring and clears the cache.
        """
        self._stop_monitoring()
        self._invalidate_cache()
        self._connected = False
        
    async def reconnect(self) -> bool:
        """Reconnect to the appliance.
        
        Returns
        -------
        bool
            True if reconnection succeeded
        """
        try:
            result = await self.is_connected()
            if result:
                # Restart monitoring if needed
                if (self._state_callbacks or self._program_finished_callbacks):
                    self._ensure_monitoring()
            return result
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Introspection helpers

    async def summary(self) -> DeviceSummary:
        """Return a fresh :class:`DeviceSummary` snapshot for this appliance.
        
        Returns
        -------
        DeviceSummary
            Current summary information
            
        Raises
        ------
        ApplianceConnectionError
            If communication with the appliance fails
        """
        # Check cache first
        cached_summary = self._get_cached("summary")
        if cached_summary is not None:
            return cached_summary
        
        # Handle simulation mode
        if self._simulation_mode != SimulationMode.DISABLED:
            sim_result = self._simulate_response("get_summary")
            if isinstance(sim_result, DeviceSummary):
                self._set_cached("summary", sim_result, ttl=5.0)
                return sim_result
            
        try:
            summary = await self._with_retry(lambda: self._client.get_summary(self.id))
            # Cache the result with a shorter TTL than other data
            self._set_cached("summary", summary, ttl=5.0)
            return summary
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to get appliance summary: {exc}") from exc

    # ------------------------------------------------------------------
    # Async context management

    async def __aenter__(self) -> Appliance:
        """Enter the async context.
        
        Returns
        -------
        Appliance
            The appliance instance
        """
        # Phase 2: Attempt to connect
        await self.reconnect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: D401
        """Exit the async context.
        
        Returns
        -------
        bool
            False to propagate exceptions
        """
        # Phase 2: Disconnect on exit
        await self.disconnect()
        return False

    # ------------------------------------------------------------------
    # Status helpers

    async def can_remote_start(self) -> bool:
        """Return True if the appliance is ready & allows remote start.
        
        Returns
        -------
        bool
            Whether remote start is possible
            
        Raises
        ------
        ApplianceConnectionError
            If communication with the appliance fails
        """
        # Check cache first
        cached_result = self._get_cached("can_remote_start")
        if cached_result is not None:
            return cached_result
            
        try:
            result = await self._client.can_remote_start(self.id)
            # Cache with a short TTL - this can change often
            self._set_cached("can_remote_start", result, ttl=3.0)
            return result
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to check remote start capability: {exc}") from exc 

    # ------------------------------------------------------------------
    # New Phase 3 configuration methods
    
    async def get_capabilities(self) -> Dict[str, Any]:
        """Return the capabilities of the appliance using the enhanced DeviceProfile system.
        
        Returns comprehensive capability information with Set-based operations
        and DeviceProfile integration.
        
        Returns
        -------
        Dict[str, Any]
            Capabilities including supported features, failed tests, and detection info
            
        Raises
        ------
        ApplianceConnectionError
            If communication with the appliance fails
        """
        # Check cache first
        if self._capabilities is not None:
            return copy.deepcopy(self._capabilities)
            
        try:
            # Use DeviceProfile if available (Phase 3 enhancement)
            if self._device_profile:
                capabilities = {
                    "device_type": self._device_profile.device_type.name,
                    "device_id": self._device_profile.device_id,
                    "friendly_name": self._device_profile.friendly_name,
                    "capabilities": {
                        "supported": [cap.name for cap in self._device_profile.capabilities],
                        "failed": [cap.name for cap in self._device_profile.failed_capabilities],
                        "detection_date": self._device_profile.capability_detection_date.isoformat() if self._device_profile.capability_detection_date else None
                    },
                    "program_catalog_available": self._device_profile.program_catalog is not None,
                    "program_catalog_method": self._device_profile.program_catalog_extraction_method
                }
                
                # Add connection information
                capabilities["connection"] = {
                    "host": self._device_profile.host,
                    "timeout": self._device_profile.timeout,
                    "wake_before_commands": self._device_profile.wake_before_commands
                }
                
                # Cache and return
                self._capabilities = capabilities
                return copy.deepcopy(capabilities)
            
            # Fallback to legacy detection method
            # Get device information
            ident = await self._client.get_device_ident(self.id)
            
            # Detect capabilities if not already done
            if self._detected_capabilities is None:
                self._detected_capabilities = await self._client.detect_capabilities(self.id)
            
            # Build capabilities dictionary
            capabilities = {
                "device_type": ident.type_id,
                "device_id": self.id,
                "model": getattr(ident, "model", "Unknown"),
                "firmware_version": getattr(ident, "firmware_version", "Unknown"),
            }
            
            # Add capability information using Set operations
            if self._detected_capabilities:
                # Convert to set if needed for consistent operations
                if not isinstance(self._detected_capabilities, set):
                    # Convert from IntFlag to Set (legacy compatibility)
                    capability_set = set()
                    for cap in DeviceCapability:
                        if cap != DeviceCapability.NONE and (self._detected_capabilities & cap):
                            capability_set.add(cap)
                    self._detected_capabilities = capability_set
                
                capabilities["capabilities"] = {
                    "supported": [cap.name for cap in self._detected_capabilities],
                    "failed": [],  # No failed capability tracking in legacy mode
                    "detection_date": None
                }
            else:
                capabilities["capabilities"] = {
                    "supported": [],
                    "failed": [],
                    "detection_date": None
                }
            
            # Check for program catalog support
            if DeviceCapability.PROGRAM_CATALOG in self._detected_capabilities:
                try:
                    programs = await self.get_available_programs()
                    capabilities["supported_programs"] = programs
                    capabilities["program_catalog_available"] = True
                except Exception as e:
                    logger.warning(f"Could not get available programs: {e}")
                    capabilities["supported_programs"] = []
                    capabilities["program_catalog_available"] = False
            else:
                capabilities["supported_programs"] = []
                capabilities["program_catalog_available"] = False
                
            # Cache capabilities (they rarely change)
            self._capabilities = capabilities
            return copy.deepcopy(capabilities)
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to get appliance capabilities: {exc}") from exc

    async def has_capability(self, capability: DeviceCapability) -> bool:
        """Check if the appliance has a specific capability.
        
        Uses DeviceProfile information if available for efficient checking,
        otherwise falls back to runtime detection.
        
        Parameters
        ----------
        capability : DeviceCapability
            The capability to check
            
        Returns
        -------
        bool
            True if the device has the capability, False otherwise
        """
        # Use DeviceProfile method if available
        if self._device_profile:
            return self._device_profile.has_capability(capability)
        
        # Fallback to detected capabilities cache
        if self._detected_capabilities is not None:
            return capability in self._detected_capabilities
        
        # Last resort: runtime detection with global detector fallback
        try:
            # Try to detect capabilities dynamically
            detected_caps, _ = await self._client.detect_capabilities_as_sets(self.id)
            self._detected_capabilities = detected_caps
            return capability in detected_caps
        except Exception as e:
            logger.warning(f"Could not detect capabilities: {e}")
            # Try to use global detector as final fallback
            return detector.has_capability(self.id, capability)
    
    def has_any_capability(self, *capabilities: DeviceCapability) -> bool:
        """Check if the appliance has any of the specified capabilities.
        
        Uses Set intersection for efficient checking.
        
        Parameters
        ----------
        *capabilities : DeviceCapability
            The capabilities to check
            
        Returns
        -------
        bool
            True if the device has any of the capabilities, False otherwise
        """
        # Use DeviceProfile method if available
        if self._device_profile:
            return self._device_profile.has_any_capability(*capabilities)
        
        # Fallback using detected capabilities
        if self._detected_capabilities is None:
            # Return False if no capabilities detected yet
            return False
        
        # Use set intersection for efficient checking
        return bool(self._detected_capabilities.intersection(capabilities))
    
    def has_all_capabilities(self, *capabilities: DeviceCapability) -> bool:
        """Check if the appliance has all of the specified capabilities.
        
        Uses Set subset operations for efficient checking.
        
        Parameters
        ----------
        *capabilities : DeviceCapability
            The capabilities to check
            
        Returns
        -------
        bool
            True if the device has all of the capabilities, False otherwise
        """
        # Use DeviceProfile method if available
        if self._device_profile:
            return self._device_profile.has_all_capabilities(*capabilities)
        
        # Fallback using detected capabilities
        if self._detected_capabilities is None:
            # Return False if no capabilities detected yet
            return False
        
        # Use set subset operations for efficient checking
        return set(capabilities).issubset(self._detected_capabilities)

    @classmethod
    async def from_profile(cls, client: MieleClient, profile: DeviceProfile) -> 'Appliance':
        """Create an Appliance instance from a device profile.
        
        Parameters
        ----------
        client : MieleClient
            The Miele API client to use
        profile : DeviceProfile
            The device profile containing configuration and capabilities
            
        Returns
        -------
        Appliance
            New Appliance instance configured with the profile
        """
        return cls(
            client=client,
            device_id=profile.device_id,
            device_profile=profile
        )

    @classmethod
    async def from_config_file(cls, config_path: str) -> 'Appliance':
        """Create an Appliance instance directly from a configuration file.
        
        This is the main factory method for the configuration-driven service architecture.
        It loads a device profile from a JSON file and creates both the client and appliance.
        
        Parameters
        ----------
        config_path : str
            Path to the device profile JSON file
            
        Returns
        -------
        Appliance
            New Appliance instance configured from the file
            
        Raises
        ------
        InvalidConfigurationError
            If the configuration file is invalid
        CorruptedConfigurationError
            If the configuration file cannot be read
        """
        # Load the device profile from JSON
        profile = load_device_profile(config_path)
        
        # Create client from profile
        client = MieleClient.from_profile(profile)
        
        # Create appliance from profile
        return await cls.from_profile(client, profile)
            
    async def get_settings(self) -> Dict[str, Any]:
        """Return all configurable settings for the appliance.
        
        Returns
        -------
        Dict[str, Any]
            All available settings and their current values
            
        Raises
        ------
        ApplianceConnectionError
            If communication with the appliance fails
        """
        # Check cache first
        cached_settings = self._get_cached("settings")
        if cached_settings is not None:
            return cached_settings
            
        try:
            # Assuming client has a method to get all settings
            settings = await self._client.get_all_settings(self.id)
            
            # Cache settings with moderate TTL
            self._set_cached("settings", settings, ttl=30.0)
            self._settings = settings  # Keep a reference
            return settings
        except Exception as exc:
            raise ApplianceConnectionError(f"Failed to get appliance settings: {exc}") from exc
            
    async def get_connection_details(self) -> Dict[str, Any]:
        """Return details about the connection to the appliance.
        
        Returns
        -------
        Dict[str, Any]
            Connection details including network info, API status, etc.
        """
        if self._connection_details is None:
            # Default connection details
            self._connection_details = {
                "connected": await self.is_connected(),
                "client_info": str(self._client),
                "device_id": self.id,
                "simulation_mode": self._simulation_mode
            }
            
        # Always update connection status
        self._connection_details["connected"] = await self.is_connected()
        return copy.deepcopy(self._connection_details)
    
    async def update_credentials(self, credentials: Credentials) -> bool:
        """Update the authentication credentials used for this appliance.
        
        Parameters
        ----------
        credentials : Credentials
            New credentials to use
            
        Returns
        -------
        bool
            True if credentials were successfully updated
        """
        try:
            # Assuming client has a method to update credentials
            await self._client.update_credentials(
                username=credentials.username,
                password=credentials.password,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret
            )
            
            # Test connection with new credentials
            return await self.is_connected()
        except Exception as exc:
            logger.error(f"Failed to update credentials: {exc}")
            return False
    
    # ------------------------------------------------------------------
    # Phase 3 testing support
    
    async def enable_simulation_mode(self, mode: str = SimulationMode.NORMAL) -> None:
        """Enable simulation mode for testing.
        
        Parameters
        ----------
        mode : str
            Simulation mode (normal or failure)
        """
        self._simulation_mode = mode
        logger.info(f"Simulation mode enabled: {mode}")
        
    async def disable_simulation_mode(self) -> None:
        """Disable simulation mode."""
        self._simulation_mode = SimulationMode.DISABLED
        logger.info("Simulation mode disabled")
        
    def _simulate_response(self, operation: str) -> Dict[str, Any]:
        """Simulate a response for testing purposes.
        
        Parameters
        ----------
        operation : str
            The operation being simulated
            
        Returns
        -------
        Dict[str, Any]
            Simulated response data
        """
        # Basic simulation responses
        if operation == "get_state":
            return {
                "status": "Ready",
                "program": None,
                "remaining_time": 0,
                "simulation": True
            }
        elif operation == "start_program":
            return {"success": True, "simulation": True}
        elif operation == "stop_program":
            return {"success": True, "simulation": True}
        else:
            return {"simulation": True, "operation": operation}
        
    # ------------------------------------------------------------------
    # Phase 3 retry logic
    
    async def _with_retry(self, operation: Callable[[], Awaitable[T]]) -> T:
        """Execute an operation with retry logic.
        
        Parameters
        ----------
        operation : Callable[[], Awaitable[T]]
            The async operation to execute with retry
            
        Returns
        -------
        T
            The result of the operation
            
        Raises
        ------
        Exception
            If all retry attempts fail
        """
        max_retries = 3
        last_exception = None
        for attempt in range(max_retries):
            try:
                return await operation()
            except Exception as e:
                last_exception = e
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Operation failed (attempt {attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        if last_exception:
            raise last_exception
        raise ApplianceError("Operation failed after retries, but no exception was raised")
    
    # ------------------------------------------------------------------
    # Phase 3 iterator support
    
    def __aiter__(self) -> 'Appliance':
        """Return self as an async iterator.
        
        This enables using the appliance in an async for loop to monitor state changes.
        
        Example
        -------
        ```python
        async for state in appliance:
            print(f"State changed: {state}")
        ```
        """
        return self
        
    async def __anext__(self) -> Dict[str, Any]:
        """Get the next state in the async iterator.
        
        This will block until the state changes or the monitoring interval elapses.
        
        Returns
        -------
        Dict[str, Any]
            Current appliance state
        """
        await asyncio.sleep(self._monitoring_interval)
        return await self.get_state() 

    # ------------------------------------------------------------------
    # Utility method for logging/debugging
            
    def export_state(self, filepath: Optional[str] = None) -> str:
        """Export current state to JSON string or file.
        
        Parameters
        ----------
        filepath : str, optional
            If provided, export state to this file
            
        Returns
        -------
        str
            JSON representation of the state
        """
        state = {
            "device_id": self.id,
            "connected": self._connected,
            "simulation_mode": self._simulation_mode,
            "cache": {
                k: v for k, v in self._cache.items() 
                if not isinstance(v, (DeviceSummary, ProgramCatalog))
            },
            "capabilities": self._capabilities,
            "settings": self._settings,
            "connection_details": self._connection_details
        }
        
        # Convert to JSON
        json_str = json.dumps(state, indent=2, default=str)
        
        # Write to file if requested
        if filepath:
            try:
                with open(filepath, "w") as f:
                    f.write(json_str)
                logger.info(f"State exported to {filepath}")
            except Exception as exc:
                logger.error(f"Failed to export state to file: {exc}")
                
        return json_str
        
    # ------------------------------------------------------------------
    # Debug and development helpers
    
    def set_log_level(self, level: int) -> None:
        """Set the log level for this appliance.
        
        Parameters
        ----------
        level : int
            Log level (e.g., logging.DEBUG, logging.INFO)
        """
        logger.setLevel(level)
        
    def __repr__(self) -> str:
        """Return a string representation of the appliance.
        
        Returns
        -------
        str
            String representation
        """
        return f"Appliance(id={self.id}, connected={self._connected}, simulation={self._simulation_mode})" 

    # ------------------------------------------------------------------
    # Phase 4 property accessors for common state information
    
    @property
    async def is_running(self) -> bool:
        """Check if a program is currently running.
        
        Returns
        -------
        bool
            True if a program is running
        """
        state = await self.get_state()
        status = state.get("status", "")
        return status in ["Running", "running", "Programmed", "programmed"]
        
    @property
    async def is_finished(self) -> bool:
        """Check if the program is finished.
        
        Returns
        -------
        bool
            True if the program is finished
        """
        state = await self.get_state()
        phase = state.get("programPhase", "")
        return phase in ["Finished", "finished"]
    
    @property
    async def remaining_time(self) -> Optional[int]:
        """Get the remaining time in minutes.
        
        Returns
        -------
        int or None
            Remaining time in minutes, or None if not available
        """
        state = await self.get_state()
        time_array = state.get("remainingTime", None)
        if not time_array or not isinstance(time_array, list) or len(time_array) < 2:
            return None
        
        # Convert [hours, minutes] to total minutes
        return time_array[0] * 60 + time_array[1]
    
    @property
    async def current_temperature(self) -> Optional[float]:
        """Get the current temperature.
        
        Returns
        -------
        float or None
            Current temperature, or None if not available
        """
        state = await self.get_state()
        temp_array = state.get("temperature", None)
        if not temp_array or not isinstance(temp_array, list) or len(temp_array) < 2:
            return None
            
        # Convert [degrees, decimals] to float (e.g., [20, 5] -> 20.5)
        return temp_array[0] + (temp_array[1] / 10)
        
    @property
    async def target_temperature(self) -> Optional[float]:
        """Get the target temperature.
        
        Returns
        -------
        float or None
            Target temperature, or None if not available
        """
        state = await self.get_state()
        temp_array = state.get("targetTemperature", None)
        if not temp_array or not isinstance(temp_array, list) or len(temp_array) < 2:
            return None
            
        # Convert [degrees, decimals] to float (e.g., [20, 5] -> 20.5)
        return temp_array[0] + (temp_array[1] / 10)
        
    @property
    async def program_phase(self) -> Optional[str]:
        """Get the current program phase.
        
        Returns
        -------
        str or None
            Current program phase, or None if not available
        """
        state = await self.get_state()
        return state.get("programPhase", None)
        
    @property
    async def status(self) -> Optional[str]:
        """Get the current status.
        
        Returns
        -------
        str or None
            Current status, or None if not available
        """
        state = await self.get_state()
        return state.get("status", None)
        
    @property
    async def is_ready(self) -> bool:
        """Check if the appliance is ready for commands.
        
        Returns
        -------
        bool
            True if the appliance is ready
        """
        return await self.can_remote_start() 

    # ------------------------------------------------------------------
    # Phase 4 batch operations
    
    async def start_with_options(self, program_name: str, **options: Any) -> None:
        """Start a program with option names instead of IDs.
        
        This is a more user-friendly way to start a program compared to
        `start_program`, as it accepts named options instead of numeric IDs.
        
        Parameters
        ----------
        program_name : str
            Name of the program to start
        **options : Any
            Named options to set (option_name=value)
            
        Raises
        ------
        ValueError
            If the program or option name is unknown
        ProgramError
            If the program cannot be started
        ApplianceConnectionError
            If communication with the appliance fails
            
        Example
        -------
        ```python
        await appliance.start_with_options(
            "Normal", temperature=60, spin_speed=1200, extra_rinse=True
        )
        ```
        """
        # Get program options to map names to IDs
        option_mappings = {}
        program_options = await self.get_program_options(program_name)
        
        # Build name -> id mapping
        for option in program_options:
            name = option.get("name", "").lower().replace(" ", "_")
            option_mappings[name] = option["id"]
            
        # Map the provided option names to IDs
        option_ids = {}
        for name, value in options.items():
            option_name = name.lower()
            if option_name not in option_mappings:
                raise ValueError(f"Unknown option '{name}' for program '{program_name}'")
                
            # Convert boolean values to 0/1
            if isinstance(value, bool):
                value = 1 if value else 0
                
            option_ids[option_mappings[option_name]] = value
            
        # Start the program with the numeric IDs
        await self.start_program(program_name, option_ids)
        
    async def batch_set_settings(self, **settings: Any) -> None:
        """Set multiple settings in a single batch operation.
        
        Parameters
        ----------
        **settings : Any
            Settings to set (setting_name=value)
            
        Raises
        ------
        ValueError
            If a setting name is unknown
        ApplianceConnectionError
            If communication with the appliance fails
            
        Example
        -------
        ```python
        await appliance.batch_set_settings(
            temperature_unit="celsius",
            display_brightness=80,
            sound_volume=2
        )
        ```
        """
        # Get all available settings to map names to IDs
        all_settings = await self.get_settings()
        
        # Build name -> id mapping
        setting_mappings = {}
        for setting_id, setting_info in all_settings.items():
            name = setting_info.get("name", "").lower().replace(" ", "_")
            setting_mappings[name] = int(setting_id)
            
        # Set each setting
        for name, value in settings.items():
            setting_name = name.lower()
            if setting_name not in setting_mappings:
                raise ValueError(f"Unknown setting '{name}'")
                
            # Convert boolean values to 0/1
            if isinstance(value, bool):
                value = 1 if value else 0
                
            # Convert string enums to their numeric value if needed
            if isinstance(value, str) and "values" in all_settings[str(setting_mappings[setting_name])]:
                value_map = {
                    val["name"].lower(): val["id"] 
                    for val in all_settings[str(setting_mappings[setting_name])]["values"]
                }
                if value.lower() in value_map:
                    value = value_map[value.lower()]
                
            await self.set_setting(setting_mappings[setting_name], value)
            
    # ------------------------------------------------------------------
    # Phase 4 configuration management
    
    async def configure(self, config: Dict[str, Any]) -> None:
        """Configure the appliance from a dictionary.
        
        This is a convenience method to configure multiple aspects of the
        appliance from a single dictionary, which could be loaded from a
        config file.
        
        Parameters
        ----------
        config : Dict[str, Any]
            Configuration dictionary with sections for different aspects
            
        Example
        -------
        ```python
        await appliance.configure({
            "settings": {
                "temperature_unit": "celsius",
                "display_brightness": 80
            },
            "monitoring": {
                "interval": 10.0,
                "callbacks": [my_callback]
            },
            "program_catalog": {
                "device_type": "washing_machine",
                "programs": [...]
            }
        })
        ```
        """
        # Process settings section
        if "settings" in config:
            await self.batch_set_settings(**config["settings"])
            
        # Process monitoring section
        if "monitoring" in config:
            if "interval" in config["monitoring"]:
                self._monitoring_interval = float(config["monitoring"]["interval"])
                
            if "callbacks" in config["monitoring"]:
                for callback in config["monitoring"]["callbacks"]:
                    await self.register_state_callback(callback)
                    
        # Process cache section
        if "cache" in config:
            if "default_ttl" in config["cache"]:
                self._default_ttl = float(config["cache"]["default_ttl"])
                
        # Process retry section
        if "retry" in config:
            if "max_retries" in config["retry"]:
                self._max_retries = int(config["retry"]["max_retries"])
                
            if "delay" in config["retry"]:
                self._retry_delay = float(config["retry"]["delay"])
        
        # Process program catalog section
        if "program_catalog" in config:
            self._custom_catalog = config["program_catalog"]
            # Invalidate program-related caches
            self._invalidate_cache("programs")
            for key in list(self._cache.keys()):
                if key.startswith("program_options_"):
                    self._invalidate_cache(key)
                
        # Process simulation section
        if "simulation" in config:
            if config["simulation"].get("enabled", False):
                mode = config["simulation"].get("mode", SimulationMode.NORMAL)
                await self.enable_simulation_mode(mode)
            else:
                await self.disable_simulation_mode()
                
        logger.info(f"Configured appliance {self.id} from dictionary")
        
    @classmethod
    async def from_config(cls, client: MieleClient, device_id: str, config: Dict[str, Any]) -> 'Appliance':
        """Create an Appliance instance from a configuration dictionary.
        
        Parameters
        ----------
        client : MieleClient
            The Miele API client to use
        device_id : str
            The device ID to control
        config : Dict[str, Any]
            Configuration dictionary
            
        Returns
        -------
        Appliance
            Configured appliance instance
        """
        # Create instance with basic settings
        simulation_mode = SimulationMode.DISABLED
        if config.get("simulation", {}).get("enabled", False):
            simulation_mode = config.get("simulation", {}).get("mode", SimulationMode.NORMAL)
            
        # Extract custom catalog if present
        custom_catalog = config.get("program_catalog")
            
        appliance = cls(
            client, 
            device_id, 
            simulation_mode=simulation_mode,
            custom_catalog=custom_catalog
        )
        
        # Apply the rest of the configuration
        await appliance.configure(config)
        
        return appliance
        
    async def save_config(self, filepath: str) -> None:
        """Save the current configuration to a JSON file.
        
        Parameters
        ----------
        filepath : str
            Path to save the configuration
        """
        config = {
            "device_id": self.id,
            "simulation": {
                "enabled": self._simulation_mode != SimulationMode.DISABLED,
                "mode": self._simulation_mode
            },
            "cache": {
                "default_ttl": self._default_ttl
            },
            "monitoring": {
                "interval": self._monitoring_interval
            },
            "retry": {
                "max_retries": self._max_retries,
                "delay": self._retry_delay
            }
        }
        
        # Include custom program catalog if available
        if self._custom_catalog is not None:
            config["program_catalog"] = self._custom_catalog
        
        # Get current settings if connected
        if self._connected:
            try:
                settings = await self.get_settings()
                # Convert to a more user-friendly format
                config["settings"] = {
                    setting.get("name", f"setting_{id}").lower().replace(" ", "_"): setting.get("value")
                    for id, setting in settings.items()
                }
            except Exception as exc:
                logger.warning(f"Could not include current settings in config: {exc}")
        
        try:
            with open(filepath, "w") as f:
                json.dump(config, f, indent=2, default=str)
            logger.info(f"Configuration saved to {filepath}")
        except Exception as exc:
            logger.error(f"Failed to save configuration: {exc}")
            raise 

    # ------------------------------------------------------------------
    # Phase 4 performance optimizations
    
    async def get_multiple_states(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple state properties in a single call.
        
        This is more efficient than making multiple individual property calls.
        
        Parameters
        ----------
        keys : List[str]
            List of state properties to retrieve
            
        Returns
        -------
        Dict[str, Any]
            Dictionary of requested state properties
            
        Example
        -------
        ```python
        states = await appliance.get_multiple_states(
            ["status", "programPhase", "remainingTime"]
        )
        print(f"Status: {states['status']}, Phase: {states['programPhase']}")
        ```
        """
        state = await self.get_state()
        return {key: state.get(key) for key in keys}
        
    async def wait_for(self, condition: Callable[[Dict[str, Any]], bool], 
                      timeout: Optional[float] = None, 
                      check_interval: float = 1.0) -> bool:
        """Wait for a specific condition to be met.
        
        Parameters
        ----------
        condition : Callable[[Dict[str, Any]], bool]
            Function that takes the current state and returns True when the condition is met
        timeout : float, optional
            Maximum time to wait in seconds, or None for no timeout
        check_interval : float
            How often to check the condition, in seconds
            
        Returns
        -------
        bool
            True if the condition was met, False if timeout occurred
            
        Example
        -------
        ```python
        # Wait for program to finish
        await appliance.wait_for(
            lambda state: state.get("programPhase") == "Finished",
            timeout=3600  # 1 hour timeout
        )
        ```
        """
        start_time = time.time()
        
        while True:
            state = await self.get_state()
            if condition(state):
                return True
                
            # Check timeout
            if timeout is not None and time.time() - start_time > timeout:
                return False
                
            await asyncio.sleep(check_interval)
            
    async def wait_until_ready(self, timeout: Optional[float] = None) -> bool:
        """Wait until the appliance is ready to accept commands.
        
        Parameters
        ----------
        timeout : float, optional
            Maximum time to wait in seconds
            
        Returns
        -------
        bool
            True if the appliance became ready, False if timeout occurred
        """
        start_time = time.time()
        
        while True:
            if await self.is_ready:
                return True
                
            # Check timeout
            if timeout is not None and time.time() - start_time > timeout:
                return False
                
            await asyncio.sleep(1.0)
            
    # ------------------------------------------------------------------
    # Phase 4 examples of common use patterns
    
    @classmethod
    async def example_basic_usage(cls, client: MieleClient, device_id: str) -> None:
        """Example of basic appliance usage.
        
        Parameters
        ----------
        client : MieleClient
            The Miele API client to use
        device_id : str
            The device ID to control
        """
        async with cls(client, device_id) as appliance:
            # Check if device is connected
            connected = await appliance.is_connected()
            print(f"Connected: {connected}")
            
            # Get current state
            state = await appliance.get_state()
            print(f"Current state: {state}")
            
            # Check if ready for remote control
            ready = await appliance.is_ready
            print(f"Ready for remote control: {ready}")
            
            # Start a program if ready
            if ready:
                await appliance.start_with_options(
                    "Normal",
                    temperature=60,
                    spin_speed=1200
                )
                print("Program started")
                
            # Wait for program to finish (with 2 hour timeout)
            finished = await appliance.wait_for(
                lambda state: state.get("programPhase") == "Finished",
                timeout=7200
            )
            print(f"Program finished: {finished}")
    
    @classmethod
    async def example_with_callbacks(cls, client: MieleClient, device_id: str) -> None:
        """Example using state change callbacks.
        
        Parameters
        ----------
        client : MieleClient
            The Miele API client to use
        device_id : str
            The device ID to control
        """
        # Define callback functions
        async def on_state_change(state: Dict[str, Any]) -> None:
            print(f"State changed: {state}")
            
        async def on_program_finished() -> None:
            print("Program finished!")
        
        # Create and use appliance
        appliance = cls(client, device_id)
        
        try:
            # Register callbacks
            await appliance.register_state_callback(on_state_change)
            await appliance.register_program_finished_callback(on_program_finished)
            
            # Start a program
            await appliance.start_program("Quick", {1: 40, 2: 1000})
            
            # Keep running until manually stopped
            try:
                while True:
                    await asyncio.sleep(10)
            except asyncio.CancelledError:
                pass
                
        finally:
            # Clean up
            await appliance.disconnect()
            
    @classmethod
    async def example_batch_operations(cls, client: MieleClient, device_id: str) -> None:
        """Example of using batch operations.
        
        Parameters
        ----------
        client : MieleClient
            The Miele API client to use
        device_id : str
            The device ID to control
        """
        async with cls(client, device_id) as appliance:
            # Configure multiple settings at once
            await appliance.batch_set_settings(
                temperature_unit="celsius",
                display_brightness=80,
                sound_volume=2
            )
            
            # Wait until device is ready
            ready = await appliance.wait_until_ready(timeout=30)
            if not ready:
                print("Device not ready after 30 seconds")
                return
                
            # Start program with user-friendly named options
            await appliance.start_with_options(
                "Eco",
                temperature=40,
                spin_speed=800,
                extra_rinse=True
            )
            
            # Get multiple state properties efficiently
            states = await appliance.get_multiple_states([
                "programPhase", "remainingTime", "temperature"
            ])
            print(f"Program: {states['programPhase']}")
            print(f"Remaining time: {states['remainingTime']}")
            print(f"Temperature: {states['temperature']}")
                
    # ------------------------------------------------------------------
    # Phase 4 API consistency improvements
    
    async def get_current_program(self) -> Optional[Dict[str, Any]]:
        """Get information about the currently running program.
        
        Returns
        -------
        Dict[str, Any] or None
            Current program information, or None if no program is running
        """
        state = await self.get_state()
        
        # Check if a program is running
        if state.get("status") not in ["Running", "running", "Programmed", "programmed"]:
            return None
            
        # Get basic program information
        program_info = {
            "status": state.get("status"),
            "phase": state.get("programPhase"),
            "remaining_time_minutes": None,
            "elapsed_time_minutes": None,
            "current_temperature": None,
            "target_temperature": None
        }
        
        # Add time information if available
        if "remainingTime" in state and isinstance(state["remainingTime"], list) and len(state["remainingTime"]) >= 2:
            program_info["remaining_time_minutes"] = state["remainingTime"][0] * 60 + state["remainingTime"][1]
            
        if "elapsedTime" in state and isinstance(state["elapsedTime"], list) and len(state["elapsedTime"]) >= 2:
            program_info["elapsed_time_minutes"] = state["elapsedTime"][0] * 60 + state["elapsedTime"][1]
            
        # Add temperature information if available
        if "temperature" in state and isinstance(state["temperature"], list) and len(state["temperature"]) >= 2:
            program_info["current_temperature"] = state["temperature"][0] + (state["temperature"][1] / 10)
            
        if "targetTemperature" in state and isinstance(state["targetTemperature"], list) and len(state["targetTemperature"]) >= 2:
            program_info["target_temperature"] = state["targetTemperature"][0] + (state["targetTemperature"][1] / 10)
            
        return program_info

    # ------------------------------------------------------------------
    # Phase 4.4 Production Readiness & Validation

    async def validate_command(self, action_type: str, action_value: int) -> Dict[str, Any]:
        """Validate if a command is supported on this device and check requirements.
        
        Parameters
        ----------
        action_type : str
            Type of action ("ProcessAction", "DeviceAction", "UserRequest")
        action_value : int
            Numeric value of the action
            
        Returns
        -------
        Dict[str, Any]
            Validation result with support status and requirements
        """
        try:
            return await self._client.validate_command(self.id, action_type, action_value)
        except Exception as exc:
            return {
                "supported": False,
                "reason": f"Validation failed: {exc}"
            }

    async def get_device_limitations(self) -> List[str]:
        """Get list of known limitations for this device.
        
        Returns
        -------
        List[str]
            List of limitation descriptions
        """
        try:
            return await self._client.get_device_limitations(self.id)
        except Exception as exc:
            logger.warning(f"Failed to get device limitations: {exc}")
            return ["Unable to determine device limitations"]

    async def get_supported_power_states(self) -> List[str]:
        """Get list of supported power states for this device.
        
        Returns
        -------
        List[str]
            List of supported power state names
        """
        try:
            return await self._client.get_supported_power_states(self.id)
        except Exception as exc:
            logger.warning(f"Failed to get supported power states: {exc}")
            return ["Active"]  # Safe default

    async def get_device_standby_behavior(self) -> str:
        """Get description of standby behavior for this device.
        
        Returns
        -------
        str
            Description of standby behavior
        """
        try:
            return await self._client.get_device_standby_behavior(self.id)
        except Exception as exc:
            logger.warning(f"Failed to get standby behavior: {exc}")
            return "Unknown standby behavior"

    async def validate_and_execute_command(self, command_func: Callable, 
                                         action_type: str, action_value: int,
                                         *args, **kwargs) -> Any:
        """Validate and execute a command with production logging.
        
        This method provides a production-ready wrapper that validates commands
        before execution and logs the results for monitoring.
        
        Parameters
        ----------
        command_func : Callable
            The command function to execute
        action_type : str
            Type of action for validation
        action_value : int
            Numeric value of the action
        *args, **kwargs
            Arguments to pass to the command function
            
        Returns
        -------
        Any
            Result of the command function
            
        Raises
        ------
        UnsupportedCapabilityError
            If the command is not supported on this device
        InvalidStateTransitionError
            If the device is not in the required state
        """
        # First validate the command
        validation = await self.validate_command(action_type, action_value)
        
        if not validation.get("supported", False):
            reason = validation.get("reason", "Command not supported")
            await self._client.log_command_execution(
                self.id, action_type, action_value, False, error=reason
            )
            raise UnsupportedCapabilityError(f"Command validation failed: {reason}")
        
        # Execute the command with logging
        try:
            result = await command_func(*args, **kwargs)
            await self._client.log_command_execution(
                self.id, action_type, action_value, True, response=result
            )
            return result
        except Exception as exc:
            await self._client.log_command_execution(
                self.id, action_type, action_value, False, error=str(exc)
            )
            raise

    async def safe_remote_start(self, **kwargs) -> bool:
        """Safely start a program with full validation and state checking.
        
        This is a production-ready version of remote_start that includes:
        - Device capability validation
        - Power state checking
        - Remote enable verification
        - Comprehensive logging
        
        Parameters
        ----------
        **kwargs
            Arguments to pass to remote_start
            
        Returns
        -------
        bool
            True if the program was started successfully
            
        Raises
        ------
        UnsupportedCapabilityError
            If the device doesn't support remote start
        InvalidStateTransitionError
            If the device is not ready for remote start
        """
        # Use the validated command execution wrapper
        try:
            await self.validate_and_execute_command(
                self.remote_start, "ProcessAction", 1, **kwargs
            )
            return True
        except Exception:
            return False

    async def safe_power_control(self, action: str) -> bool:
        """Safely control device power with validation.
        
        Parameters
        ----------
        action : str
            Power action ('on', 'off', 'standby')
            
        Returns
        -------
        bool
            True if the power action was successful
        """
        action_map = {
            'on': (self.power_on, "DeviceAction", 1),
            'off': (self.power_off, "DeviceAction", 2),  # May fallback to DOP2
            'standby': (self.standby, "DeviceAction", 2)
        }
        
        if action not in action_map:
            raise ValueError(f"Unknown power action '{action}'. Valid: {list(action_map.keys())}")
        
        command_func, action_type, action_value = action_map[action]
        
        try:
            await self.validate_and_execute_command(
                command_func, action_type, action_value
            )
            return True
        except Exception:
            return False

    async def get_device_health(self) -> Dict[str, Any]:
        """Get comprehensive device health information.
        
        This method provides a production monitoring view of device status
        including power state, connectivity, capabilities, and limitations.
        
        Returns
        -------
        Dict[str, Any]
            Comprehensive device health report
        """
        try:
            # Get basic status
            connected = await self.is_connected()
            state = await self.get_state() if connected else {}
            power_state = await self.get_power_state() if connected else "Unknown"
            
            # Get device information
            limitations = await self.get_device_limitations()
            supported_power_states = await self.get_supported_power_states()
            standby_behavior = await self.get_device_standby_behavior()
            
            # Get capabilities
            capabilities = await self.get_capabilities()
            
            # Check if ready for operations
            ready = await self.is_ready if connected else False
            
            health = {
                "device_id": self.id,
                "timestamp": datetime.utcnow().isoformat(),
                "connectivity": {
                    "connected": connected,
                    "power_state": power_state,
                    "ready_for_commands": ready
                },
                "capabilities": {
                    "supported": capabilities.get("capabilities", {}).get("supported", []),
                    "failed": capabilities.get("capabilities", {}).get("failed", [])
                },
                "device_info": {
                    "type": capabilities.get("device_type", "Unknown"),
                    "limitations": limitations,
                    "supported_power_states": supported_power_states,
                    "standby_behavior": standby_behavior
                },
                "current_state": {
                    "status": state.get("status", "Unknown"),
                    "program_phase": state.get("programPhase"),
                    "standby_state": state.get("StandbyState"),
                    "errors": await self.get_error_status() if connected else {}
                },
                "configuration": {
                    "simulation_mode": self._simulation_mode,
                    "cache_enabled": len(self._cache) > 0,
                    "monitoring_active": self._monitoring_task is not None and not self._monitoring_task.done()
                }
            }
            
            return health
            
        except Exception as exc:
            logger.error(f"Failed to get device health: {exc}")
            return {
                "device_id": self.id,
                "timestamp": datetime.utcnow().isoformat(),
                "error": f"Health check failed: {exc}",
                "connectivity": {"connected": False}
            }

    # ------------------------------------------------------------------
    # Phase 4 API Polish - Convenience Methods

    async def get_device_info_summary(self) -> Dict[str, Any]:
        """Get a concise summary of device information for dashboards.
        
        Returns
        -------
        Dict[str, Any]
            Concise device information summary
        """
        try:
            summary = await self.summary()
            capabilities = await self.get_capabilities()
            limitations = await self.get_device_limitations()
            
            return {
                "device_id": self.id,
                "name": summary.name if summary else "Unknown Device",
                "type": capabilities.get("device_type", "Unknown"),
                "status": summary.state.status if summary and summary.state else "Unknown",
                "connected": await self.is_connected(),
                "ready": await self.is_ready,
                "power_state": await self.get_power_state(),
                "limitations_count": len(limitations),
                "capabilities_count": len(capabilities.get("capabilities", {}).get("supported", [])),
                "last_updated": datetime.utcnow().isoformat()
            }
        except Exception as exc:
            return {
                "device_id": self.id,
                "error": str(exc),
                "connected": False,
                "last_updated": datetime.utcnow().isoformat()
            } 