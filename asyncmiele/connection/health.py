"""
Connection health monitoring for Miele devices.
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Set, Callable, Awaitable, Any, List, Tuple
from enum import Enum

from asyncmiele.exceptions.connection import ConnectionHealthError

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Possible states for a device connection."""
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ConnectionHealthMonitor:
    """Monitors the health of connections to Miele devices.
    
    This class provides health check functionality to periodically test
    connections to devices and report their status.
    """
    
    def __init__(
        self,
        check_interval: float = 60.0,
        degraded_threshold: int = 2,
        unhealthy_threshold: int = 5,
        recovery_threshold: int = 3
    ) -> None:
        """Initialize the connection health monitor.
        
        Args:
            check_interval: Interval between health checks (seconds)
            degraded_threshold: Number of failed checks before marking as degraded
            unhealthy_threshold: Number of failed checks before marking as unhealthy
            recovery_threshold: Number of successful checks before recovery
        """
        self._check_interval = check_interval
        self._degraded_threshold = degraded_threshold
        self._unhealthy_threshold = unhealthy_threshold
        self._recovery_threshold = recovery_threshold
        
        # Maps device_id -> (state, fail_count, success_count, last_check_time)
        self._health_states: Dict[str, Tuple[ConnectionState, int, int, float]] = {}
        
        # Health check callbacks: device_id -> callback function
        self._health_checks: Dict[str, Callable[[], Awaitable[bool]]] = {}
        
        # State change callbacks
        self._state_callbacks: Dict[str, List[Callable[[str, ConnectionState], Awaitable[None]]]] = {}
        
        # Monitor task
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
    async def start(self) -> None:
        """Start the health monitoring."""
        if self._running:
            return
            
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.debug("Connection health monitoring started")
        
    async def stop(self) -> None:
        """Stop the health monitoring."""
        if not self._running:
            return
            
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
            
        logger.debug("Connection health monitoring stopped")
        
    def register_health_check(
        self, 
        device_id: str, 
        check_callback: Callable[[], Awaitable[bool]]
    ) -> None:
        """Register a health check callback for a device.
        
        Args:
            device_id: ID of the device to monitor
            check_callback: Async callback that returns True if healthy, False otherwise
        """
        self._health_checks[device_id] = check_callback
        
        # Initialize health state if not already present
        if device_id not in self._health_states:
            self._health_states[device_id] = (ConnectionState.UNKNOWN, 0, 0, time.time())
            
    def unregister_health_check(self, device_id: str) -> None:
        """Unregister a health check callback.
        
        Args:
            device_id: ID of the device to stop monitoring
        """
        if device_id in self._health_checks:
            del self._health_checks[device_id]
            
    def register_state_callback(
        self, 
        device_id: str, 
        callback: Callable[[str, ConnectionState], Awaitable[None]]
    ) -> None:
        """Register a callback for connection state changes.
        
        Args:
            device_id: ID of the device to monitor
            callback: Async callback that receives (device_id, new_state)
        """
        if device_id not in self._state_callbacks:
            self._state_callbacks[device_id] = []
            
        self._state_callbacks[device_id].append(callback)
        
    def unregister_state_callback(
        self, 
        device_id: str, 
        callback: Callable[[str, ConnectionState], Awaitable[None]]
    ) -> None:
        """Unregister a state change callback.
        
        Args:
            device_id: ID of the device
            callback: Callback to unregister
        """
        if device_id in self._state_callbacks and callback in self._state_callbacks[device_id]:
            self._state_callbacks[device_id].remove(callback)
            
            if not self._state_callbacks[device_id]:
                del self._state_callbacks[device_id]
                
    def get_connection_state(self, device_id: str) -> ConnectionState:
        """Get the current connection state for a device.
        
        Args:
            device_id: ID of the device
            
        Returns:
            Current connection state
        """
        if device_id in self._health_states:
            return self._health_states[device_id][0]
        return ConnectionState.UNKNOWN
        
    def mark_connection_healthy(self, device_id: str) -> None:
        """Manually mark a connection as healthy.
        
        Args:
            device_id: ID of the device
        """
        old_state = self.get_connection_state(device_id)
        self._health_states[device_id] = (ConnectionState.HEALTHY, 0, self._recovery_threshold, time.time())
        
        # Notify callbacks if state changed
        if old_state != ConnectionState.HEALTHY:
            self._notify_state_change(device_id, ConnectionState.HEALTHY)
            
    def mark_connection_unhealthy(self, device_id: str) -> None:
        """Manually mark a connection as unhealthy.
        
        Args:
            device_id: ID of the device
        """
        old_state = self.get_connection_state(device_id)
        self._health_states[device_id] = (ConnectionState.UNHEALTHY, self._unhealthy_threshold, 0, time.time())
        
        # Notify callbacks if state changed
        if old_state != ConnectionState.UNHEALTHY:
            self._notify_state_change(device_id, ConnectionState.UNHEALTHY)
            
    async def check_health(self, device_id: str) -> bool:
        """Check the health of a specific device.
        
        Args:
            device_id: ID of the device to check
            
        Returns:
            True if the device is healthy, False otherwise
            
        Raises:
            ConnectionHealthError: If no health check is registered for the device
        """
        if device_id not in self._health_checks:
            raise ConnectionHealthError(f"No health check registered for device {device_id}")
            
        try:
            is_healthy = await self._health_checks[device_id]()
            await self._update_health_state(device_id, is_healthy)
            return is_healthy
        except Exception as e:
            logger.error(f"Health check failed for device {device_id}: {e}")
            await self._update_health_state(device_id, False)
            return False
            
    async def _update_health_state(self, device_id: str, is_healthy: bool) -> None:
        """Update the health state based on a check result.
        
        Args:
            device_id: ID of the device
            is_healthy: Whether the health check succeeded
        """
        if device_id not in self._health_states:
            self._health_states[device_id] = (ConnectionState.UNKNOWN, 0, 0, time.time())
            
        current_state, fail_count, success_count, last_check = self._health_states[device_id]
        
        if is_healthy:
            # Successful check
            fail_count = 0
            success_count += 1
            
            # Check if we've recovered
            if current_state != ConnectionState.HEALTHY and success_count >= self._recovery_threshold:
                new_state = ConnectionState.HEALTHY
                self._health_states[device_id] = (new_state, fail_count, success_count, time.time())
                
                # Notify state change
                if new_state != current_state:
                    await self._notify_state_change(device_id, new_state)
                    
            else:
                # Just update counts
                self._health_states[device_id] = (current_state, fail_count, success_count, time.time())
                
        else:
            # Failed check
            fail_count += 1
            success_count = 0
            
            # Determine new state based on fail count
            new_state = current_state
            if fail_count >= self._unhealthy_threshold:
                new_state = ConnectionState.UNHEALTHY
            elif fail_count >= self._degraded_threshold:
                new_state = ConnectionState.DEGRADED
                
            self._health_states[device_id] = (new_state, fail_count, success_count, time.time())
            
            # Notify state change
            if new_state != current_state:
                await self._notify_state_change(device_id, new_state)
                
    async def _monitoring_loop(self) -> None:
        """Background task to periodically check health of all devices."""
        while self._running:
            try:
                # Create list of devices to check
                devices = list(self._health_checks.keys())
                
                for device_id in devices:
                    # Skip devices we no longer have checks for
                    if device_id not in self._health_checks:
                        continue
                        
                    # Check if it's time to check this device
                    if device_id in self._health_states:
                        _, _, _, last_check = self._health_states[device_id]
                        if time.time() - last_check < self._check_interval:
                            continue
                            
                    # Perform health check
                    try:
                        await self.check_health(device_id)
                    except Exception as e:
                        logger.error(f"Error checking health for device {device_id}: {e}")
                        
                # Sleep for a bit before checking again
                await asyncio.sleep(1.0)
                
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(self._check_interval / 4)
                
    async def _notify_state_change(self, device_id: str, new_state: ConnectionState) -> None:
        """Notify callbacks about a state change.
        
        Args:
            device_id: ID of the device
            new_state: New connection state
        """
        logger.info(f"Connection state for device {device_id} changed to {new_state.value}")
        
        if device_id in self._state_callbacks:
            for callback in self._state_callbacks[device_id]:
                try:
                    await callback(device_id, new_state)
                except Exception as e:
                    logger.error(f"Error in state change callback for device {device_id}: {e}")
                    
    def get_all_states(self) -> Dict[str, ConnectionState]:
        """Get the current state of all monitored connections.
        
        Returns:
            Dict mapping device IDs to connection states
        """
        return {device_id: state_info[0] for device_id, state_info in self._health_states.items()} 