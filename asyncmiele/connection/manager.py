"""
Connection manager for optimized device connections.

This module provides a central connection manager that handles connection pooling,
health monitoring, and automatic reconnection.
"""

import asyncio
import logging
from typing import Dict, Optional, Any, Set, Callable, Awaitable, List, Tuple, TypeVar, Generic

import aiohttp

from asyncmiele.connection.pool import ConnectionPool
from asyncmiele.connection.health import ConnectionHealthMonitor, ConnectionState
from asyncmiele.models.device_profile import DeviceProfile
from asyncmiele.exceptions.connection import ConnectionLostError, ReconnectionError
from asyncmiele.api.client import MieleClient
from asyncmiele.exceptions.network import NetworkConnectionError, NetworkTimeoutError
from asyncmiele.exceptions.connection import ConnectionException

logger = logging.getLogger(__name__)

# Type variable for generic return types
T = TypeVar('T')


class ConnectionManager:
    """Central manager for Miele device connections.
    
    This class integrates connection pooling, health monitoring, and automatic
    reconnection to provide optimized and robust connections to Miele devices.
    """
    
    def __init__(
        self,
        max_connections: int = 10,
        connection_timeout: float = 10.0,
        health_check_interval: float = 60.0,
        retry_count: int = 3,
        retry_delay: float = 2.0
    ) -> None:
        """Initialize the connection manager.
        
        Args:
            max_connections: Maximum number of connections in the pool
            connection_timeout: Timeout for establishing new connections (seconds)
            health_check_interval: Interval between health checks (seconds)
            retry_count: Number of retry attempts for failed operations
            retry_delay: Delay between retry attempts (seconds)
        """
        self._connection_pool = ConnectionPool(
            max_connections=max_connections,
            connection_timeout=connection_timeout
        )
        
        self._health_monitor = ConnectionHealthMonitor(
            check_interval=health_check_interval
        )
        
        self._retry_count = retry_count
        self._retry_delay = retry_delay
        
        # Active clients
        self._clients: Dict[str, MieleClient] = {}
        
        # Device profiles
        self._profiles: Dict[str, DeviceProfile] = {}
        
        # Running state
        self._running = False
        
    async def start(self) -> None:
        """Start the connection manager."""
        if self._running:
            return
            
        self._running = True
        
        # Start pool and monitor
        await self._connection_pool.start()
        await self._health_monitor.start()
        
        logger.debug("Connection manager started")
        
    async def stop(self) -> None:
        """Stop the connection manager and close all connections."""
        if not self._running:
            return
            
        self._running = False
        
        # Stop pool and monitor
        await self._health_monitor.stop()
        await self._connection_pool.stop()
        
        # Close all clients
        for client in self._clients.values():
            await client.close()
            
        self._clients.clear()
        logger.debug("Connection manager stopped")
        
    async def get_client(self, device_id: str, profile: Optional[DeviceProfile] = None) -> MieleClient:
        """Get a client for a device.
        
        Args:
            device_id: ID of the device
            profile: Optional device profile
            
        Returns:
            MieleClient: Client for the device
            
        Raises:
            ConnectionLostError: If the connection is lost and cannot be reconnected
        """
        # Check if we already have a client for this device
        if device_id in self._clients:
            return self._clients[device_id]
            
        # Use provided profile or existing one
        if profile:
            self._profiles[device_id] = profile
        elif device_id not in self._profiles:
            raise ValueError(f"No profile found for device {device_id}")
            
        profile = self._profiles[device_id]
        
        # Create a new client
        client = MieleClient.from_profile(profile)
        
        # Register health check
        self._register_health_check(device_id, client)
        
        # Store client
        self._clients[device_id] = client
        
        return client
        
    def _register_health_check(self, device_id: str, client: MieleClient) -> None:
        """Register a health check for a device.
        
        Args:
            device_id: ID of the device
            client: MieleClient for the device
        """
        async def health_check() -> bool:
            try:
                # Simple health check by getting device identification
                await client.get_device_ident(device_id)
                return True
            except Exception:
                return False
                
        self._health_monitor.register_health_check(device_id, health_check)
        
        # Register reconnection callback
        async def on_state_change(d_id: str, new_state: ConnectionState) -> None:
            if new_state == ConnectionState.UNHEALTHY:
                # Try to reconnect
                logger.warning(f"Connection to device {d_id} is unhealthy, attempting reconnection")
                await self._try_reconnect(d_id)
                
        self._health_monitor.register_state_callback(device_id, on_state_change)
        
    async def execute_with_retry(
        self, 
        device_id: str, 
        operation: Callable[[], Awaitable[T]],
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None
    ) -> T:
        """Execute an operation with automatic retry.
        
        Args:
            device_id: ID of the device
            operation: Async operation to execute
            max_retries: Maximum number of retries (defaults to manager's setting)
            retry_delay: Delay between retries (defaults to manager's setting)
            
        Returns:
            Result of the operation
            
        Raises:
            ConnectionLostError: If all retries fail
            ReconnectionError: If reconnection fails
            Various other exceptions based on the operation
        """
        # Use manager defaults if not specified
        max_retries = max_retries if max_retries is not None else self._retry_count
        retry_delay = retry_delay if retry_delay is not None else self._retry_delay
        
        last_exception = None
        retries = 0
        
        while retries <= max_retries:
            try:
                # Check if connection is unhealthy before even trying
                if self._health_monitor.get_connection_state(device_id) == ConnectionState.UNHEALTHY:
                    if not await self._try_reconnect(device_id):
                        raise ReconnectionError(f"Cannot reconnect to device {device_id}")
                
                # Execute operation
                result = await operation()
                
                # If successful, mark connection as healthy
                self._health_monitor.mark_connection_healthy(device_id)
                
                return result
                
            except Exception as e:
                last_exception = e
                retries += 1
                
                # If retries left, try to reconnect and retry
                if retries <= max_retries:
                    logger.warning(
                        f"Operation failed for device {device_id}, "
                        f"retrying ({retries}/{max_retries}): {e}"
                    )
                    
                    # Only try to reconnect if it seems like a connection issue
                    if self._is_connection_error(e):
                        await self._try_reconnect(device_id)
                        
                    # Wait before retrying
                    if retry_delay > 0:
                        await asyncio.sleep(retry_delay * (2 ** (retries - 1)))  # Exponential backoff
                else:
                    # Mark connection as unhealthy if all retries failed
                    self._health_monitor.mark_connection_unhealthy(device_id)
                    break
        
        # If we get here, all retries failed
        raise ConnectionLostError(f"Operation failed after {max_retries} retries: {last_exception}")
        
    def _is_connection_error(self, exception: Exception) -> bool:
        """Check if an exception indicates a connection error.
        
        Args:
            exception: Exception to check
            
        Returns:
            True if it's likely a connection error
        """
        # Check for common connection error types
        if isinstance(exception, (NetworkConnectionError, NetworkTimeoutError, ConnectionException)):
            return True
            
        # Check for aiohttp connection errors
        if isinstance(exception, (aiohttp.ClientConnectionError, aiohttp.ClientResponseError)):
            return True
            
        # Check error message for common connection issues
        error_msg = str(exception).lower()
        connection_keywords = [
            "connection", "timeout", "refused", "reset", "closed", "broken", "pipe", 
            "eof", "unreachable", "network", "host"
        ]
        
        return any(keyword in error_msg for keyword in connection_keywords)
        
    async def _try_reconnect(self, device_id: str) -> bool:
        """Attempt to reconnect to a device.
        
        Args:
            device_id: Device to reconnect to
            
        Returns:
            True if reconnection was successful
        """
        try:
            if device_id not in self._profiles:
                logger.error(f"Cannot reconnect to {device_id}: no profile available")
                return False
            
            profile = self._profiles[device_id]
            
            # Close existing client if any
            if device_id in self._clients:
                await self._clients[device_id].close()
                del self._clients[device_id]
            
            # Create a new client
            new_client = MieleClient.from_profile(profile)
            
            # Test connection
            await new_client.get_device_ident(device_id)
            
            # Update client
            self._clients[device_id] = new_client
            
            # Mark as healthy
            self._health_monitor.mark_connection_healthy(device_id)
            
            logger.info(f"Successfully reconnected to device {device_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reconnect to device {device_id}: {e}")
            return False
            
    def get_health_monitor(self) -> ConnectionHealthMonitor:
        """Get the connection health monitor.
        
        Returns:
            The health monitor instance
        """
        return self._health_monitor
        
    def get_connection_pool(self) -> ConnectionPool:
        """Get the connection pool.
        
        Returns:
            The connection pool instance
        """
        return self._connection_pool
        
    def get_connection_state(self, device_id: str) -> ConnectionState:
        """Get the connection state for a device.
        
        Args:
            device_id: ID of the device
            
        Returns:
            Current connection state
        """
        return self._health_monitor.get_connection_state(device_id)
        
    def has_client(self, device_id: str) -> bool:
        """Check if a client exists for a device.
        
        Args:
            device_id: ID of the device
            
        Returns:
            True if a client exists
        """
        return device_id in self._clients
        
    async def close_client(self, device_id: str) -> None:
        """Close a client for a device.
        
        Args:
            device_id: ID of the device
        """
        if device_id in self._clients:
            await self._clients[device_id].close()
            del self._clients[device_id]
            
        # Unregister health check
        self._health_monitor.unregister_health_check(device_id)
        
    async def __aenter__(self) -> 'ConnectionManager':
        """Enter the async context.
        
        Returns:
            The connection manager instance
        """
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Exit the async context.
        
        Args:
            exc_type: Exception type
            exc: Exception
            tb: Traceback
        """
        await self.stop()
        
    def create_client_from_profile(self, profile: DeviceProfile) -> MieleClient:
        """Create a client from a device profile (Phase 3 enhancement).
        
        This method provides direct DeviceProfile support for the configuration-driven
        service architecture.
        
        Args:
            profile: DeviceProfile with complete device configuration
            
        Returns:
            MieleClient configured from the profile
        """
        return MieleClient.from_profile(profile)
    
    def validate_profile(self, profile: DeviceProfile) -> bool:
        """Validate a DeviceProfile configuration (Phase 3 enhancement).
        
        Validates that the profile contains all necessary information for
        creating a working client connection.
        
        Args:
            profile: DeviceProfile to validate
            
        Returns:
            True if the profile is valid, False otherwise
        """
        try:
            # Test basic model validation
            profile.model_validate(profile.model_dump())
            
            # Test credential format
            if not profile.credentials.group_id or not profile.credentials.group_key:
                return False
            
            # Test connection parameters (direct access from DeviceProfile)
            if not profile.host or not profile.device_id:
                return False
            
            # Test timeout value
            if profile.timeout <= 0:
                return False
                
            return True
        except Exception:
            return False
    
    async def add_device_from_profile(self, profile: DeviceProfile) -> MieleClient:
        """Add a device to the connection manager from a DeviceProfile (Phase 3 enhancement).
        
        This is the primary method for adding devices in the configuration-driven
        service architecture.
        
        Args:
            profile: Complete DeviceProfile configuration
            
        Returns:
            MieleClient for the device
            
        Raises:
            ValueError: If the profile is invalid
            ConnectionLostError: If connection cannot be established
        """
        # Validate profile first
        if not self.validate_profile(profile):
            raise ValueError(f"Invalid device profile for device {profile.device_id}")
        
        # Store profile and get client
        return await self.get_client(profile.device_id, profile)
    
    async def get_device_capabilities(self, device_id: str) -> Dict[str, Any]:
        """Get comprehensive capability information for a device (Phase 3 enhancement).
        
        Uses DeviceProfile information when available for efficient capability reporting.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Comprehensive capability information including supported and failed capabilities
        """
        # Check if we have a profile with capability information
        if device_id in self._profiles:
            profile = self._profiles[device_id]
            return {
                "supported": [cap.name for cap in profile.capabilities],
                "failed": [cap.name for cap in profile.failed_capabilities],
                "detection_date": profile.capability_detection_date.isoformat() if profile.capability_detection_date else None,
                "source": "device_profile"
            }
        
        # Fallback to client-based detection if profile not available
        if device_id in self._clients:
            client = self._clients[device_id]
            try:
                supported, failed = await client.detect_capabilities_as_sets(device_id)
                return {
                    "supported": [cap.name for cap in supported],
                    "failed": [cap.name for cap in failed],
                    "detection_date": None,
                    "source": "runtime_detection"
                }
            except Exception as e:
                logger.warning(f"Failed to detect capabilities for {device_id}: {e}")
                return {
                    "supported": [],
                    "failed": [],
                    "detection_date": None,
                    "source": "detection_failed"
                }
        
        raise ValueError(f"No client or profile found for device {device_id}") 