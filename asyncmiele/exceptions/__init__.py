"""
Exceptions for the asyncmiele library.
"""

from typing import Iterable


class MieleException(Exception):
    """Base exception for all asyncmiele-related errors."""
    pass


__all__: Iterable[str] = [
    'MieleException',
]

# Import specific exceptions for re-export
from asyncmiele.exceptions.api import APIException, DeviceNotFoundError, DecryptionError, ParseError
from asyncmiele.exceptions.auth import AuthenticationException, InvalidCredentialsError, AuthorizationError, RegistrationError
from asyncmiele.exceptions.network import NetworkException, NetworkConnectionError, NetworkTimeoutError, ResponseError
from asyncmiele.exceptions.config import ConfigurationError, UnsupportedCapabilityError, DeviceConfigurationError, ValidationError
from asyncmiele.exceptions.connection import ConnectionException, ConnectionLostError, ReconnectionError, ConnectionPoolExhaustedError, DeviceResetError, DeviceSleepError, ConnectionHealthError
from asyncmiele.exceptions.setup import SetupError, WifiConfigurationError, ProvisioningError, DeviceNotInSetupModeError, AccessPointConnectionError

# Add them to __all__ for proper import exposure
__all__ += [
    'APIException', 'DeviceNotFoundError', 'DecryptionError', 'ParseError',
    'AuthenticationException', 'InvalidCredentialsError', 'AuthorizationError', 'RegistrationError',
    'NetworkException', 'NetworkConnectionError', 'NetworkTimeoutError', 'ResponseError',
    'ConfigurationError', 'UnsupportedCapabilityError', 'DeviceConfigurationError', 'ValidationError',
    'ConnectionException', 'ConnectionLostError', 'ReconnectionError', 'ConnectionPoolExhaustedError',
    'DeviceResetError', 'DeviceSleepError', 'ConnectionHealthError',
    'SetupError', 'WifiConfigurationError', 'ProvisioningError', 'DeviceNotInSetupModeError', 'AccessPointConnectionError',
]
