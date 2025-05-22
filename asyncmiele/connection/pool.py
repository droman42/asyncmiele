"""
Connection pool for managing multiple device connections efficiently.
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Set, Tuple, Any
import weakref

import aiohttp

from asyncmiele.exceptions.connection import ConnectionPoolExhaustedError
from asyncmiele.models.device_profile import DeviceProfile

logger = logging.getLogger(__name__)


class ConnectionPool:
    """Manages a pool of connections to Miele devices.
    
    This class optimizes connection usage by maintaining a pool of connections
    that can be reused across multiple requests, reducing overhead and
    improving performance for applications that frequently communicate with
    the same set of devices.
    """
    
    def __init__(
        self, 
        max_connections: int = 10,
        connection_timeout: float = 10.0,
        idle_timeout: float = 60.0,
        max_lifetime: float = 300.0
    ) -> None:
        """Initialize the connection pool.
        
        Args:
            max_connections: Maximum number of connections in the pool
            connection_timeout: Timeout for establishing new connections (seconds)
            idle_timeout: Time after which idle connections are closed (seconds)
            max_lifetime: Maximum lifetime of a connection (seconds)
        """
        self._max_connections = max_connections
        self._connection_timeout = connection_timeout
        self._idle_timeout = idle_timeout
        self._max_lifetime = max_lifetime
        
        # Connection pool: Maps device_id -> (session, last_used_timestamp, created_timestamp)
        self._pool: Dict[str, Tuple[aiohttp.ClientSession, float, float]] = {}
        
        # Active connections currently in use
        self._in_use: Set[str] = set()
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
    async def start(self) -> None:
        """Start the connection pool and background cleanup task."""
        if self._running:
            return
            
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.debug("Connection pool started")
        
    async def stop(self) -> None:
        """Stop the connection pool and close all connections."""
        if not self._running:
            return
            
        self._running = False
        
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            
        # Close all connections
        for device_id, (session, _, _) in list(self._pool.items()):
            await self._close_connection(device_id, session)
            
        self._pool.clear()
        self._in_use.clear()
        logger.debug("Connection pool stopped")
        
    async def acquire(self, device_id: str, profile: Optional[DeviceProfile] = None) -> aiohttp.ClientSession:
        """Acquire a connection for a device.
        
        Args:
            device_id: ID of the device to connect to
            profile: Optional device profile with connection settings
            
        Returns:
            aiohttp.ClientSession: Client session for the device
            
        Raises:
            ConnectionPoolExhaustedError: If the pool is exhausted
        """
        # Check if we already have a connection for this device
        if device_id in self._pool:
            session, last_used, created = self._pool[device_id]
            
            # Check if the connection is still valid
            if time.time() - created > self._max_lifetime:
                # Connection too old, close and create a new one
                await self._close_connection(device_id, session)
                del self._pool[device_id]
            else:
                # Mark as in use and return
                self._in_use.add(device_id)
                # Update last used timestamp
                self._pool[device_id] = (session, time.time(), created)
                return session
                
        # Need to create a new connection
        if len(self._pool) >= self._max_connections:
            # Try to find an idle connection to close
            for idle_id, (idle_session, last_used, _) in list(self._pool.items()):
                if idle_id not in self._in_use and time.time() - last_used > self._idle_timeout:
                    await self._close_connection(idle_id, idle_session)
                    del self._pool[idle_id]
                    break
            else:
                # No idle connections to close
                if len(self._pool) >= self._max_connections:
                    raise ConnectionPoolExhaustedError(
                        f"Connection pool exhausted (max: {self._max_connections})"
                    )
                    
        # Create a new connection
        timeout = aiohttp.ClientTimeout(total=self._connection_timeout)
        
        # Use profile-specific settings if provided
        if profile and profile.config:
            conn_timeout = getattr(profile.config, 'connection_timeout', self._connection_timeout)
            timeout = aiohttp.ClientTimeout(total=conn_timeout)
            
        # Create new session
        session = aiohttp.ClientSession(timeout=timeout)
        
        # Add to pool
        now = time.time()
        self._pool[device_id] = (session, now, now)
        self._in_use.add(device_id)
        
        return session
        
    async def release(self, device_id: str) -> None:
        """Release a connection back to the pool.
        
        Args:
            device_id: ID of the device whose connection to release
        """
        if device_id in self._in_use:
            self._in_use.remove(device_id)
            
        # Update last used timestamp
        if device_id in self._pool:
            session, _, created = self._pool[device_id]
            self._pool[device_id] = (session, time.time(), created)
            
    async def close(self, device_id: str) -> None:
        """Close a specific connection.
        
        Args:
            device_id: ID of the device whose connection to close
        """
        if device_id in self._pool:
            session, _, _ = self._pool[device_id]
            await self._close_connection(device_id, session)
            del self._pool[device_id]
            
        if device_id in self._in_use:
            self._in_use.remove(device_id)
            
    async def _close_connection(self, device_id: str, session: aiohttp.ClientSession) -> None:
        """Close a connection and handle exceptions.
        
        Args:
            device_id: ID of the device
            session: Session to close
        """
        try:
            if not session.closed:
                await session.close()
            logger.debug(f"Closed connection for device {device_id}")
        except Exception as e:
            logger.warning(f"Error closing connection for device {device_id}: {e}")
            
    async def _cleanup_loop(self) -> None:
        """Background task to clean up idle and expired connections."""
        while self._running:
            try:
                # Close idle connections
                for device_id, (session, last_used, created) in list(self._pool.items()):
                    # Skip connections in use
                    if device_id in self._in_use:
                        continue
                        
                    now = time.time()
                    
                    # Close expired connections
                    if now - created > self._max_lifetime:
                        logger.debug(f"Closing expired connection for device {device_id}")
                        await self._close_connection(device_id, session)
                        del self._pool[device_id]
                        
                    # Close idle connections
                    elif now - last_used > self._idle_timeout:
                        logger.debug(f"Closing idle connection for device {device_id}")
                        await self._close_connection(device_id, session)
                        del self._pool[device_id]
                        
            except Exception as e:
                logger.error(f"Error in connection pool cleanup: {e}")
                
            # Sleep for a while
            await asyncio.sleep(min(self._idle_timeout, self._max_lifetime) / 4)
            
    def __len__(self) -> int:
        """Return the number of connections in the pool."""
        return len(self._pool)
        
    @property
    def active_connections(self) -> int:
        """Return the number of active connections."""
        return len(self._in_use)
        
    @property
    def idle_connections(self) -> int:
        """Return the number of idle connections."""
        return len(self._pool) - len(self._in_use) 