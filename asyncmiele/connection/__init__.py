"""
Connection optimization module for asyncmiele.

This module provides enhanced connection management for Miele devices,
including connection pooling, automatic reconnection, and health monitoring.
"""

from asyncmiele.connection.manager import ConnectionManager
from asyncmiele.connection.pool import ConnectionPool
from asyncmiele.connection.health import ConnectionHealthMonitor
from asyncmiele.connection.reset import DeviceResetter

__all__ = [
    'ConnectionManager',
    'ConnectionPool',
    'ConnectionHealthMonitor',
    'DeviceResetter',
] 