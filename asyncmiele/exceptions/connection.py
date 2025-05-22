"""
Connection-related exceptions for optimized device connections.
"""

from asyncmiele.exceptions import MieleException
from asyncmiele.exceptions.network import NetworkException


class ConnectionException(NetworkException):
    """Base class for connection-related errors."""
    pass


class ConnectionLostError(ConnectionException):
    """Raised when an established connection to a device is lost."""
    pass


class ReconnectionError(ConnectionException):
    """Raised when attempts to reconnect to a device fail."""
    pass


class ConnectionPoolExhaustedError(ConnectionException):
    """Raised when the connection pool is exhausted."""
    pass


class DeviceResetError(ConnectionException):
    """Raised when an error occurs during device reset operations."""
    pass


class DeviceSleepError(ConnectionException):
    """Raised when a device is in sleep mode and cannot process commands."""
    pass


class ConnectionHealthError(ConnectionException):
    """Raised when connection health check fails."""
    pass 