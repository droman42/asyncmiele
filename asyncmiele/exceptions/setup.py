"""
Exceptions related to device setup and provisioning.
"""

from asyncmiele.exceptions import MieleException


class SetupError(MieleException):
    """Base class for all setup-related exceptions."""
    pass


class WifiConfigurationError(SetupError):
    """Raised when WiFi configuration fails."""
    pass


class ProvisioningError(SetupError):
    """Raised when security credentials provisioning fails."""
    pass


class DeviceNotInSetupModeError(SetupError):
    """Raised when a device is not in setup mode when expected."""
    pass


class AccessPointConnectionError(SetupError):
    """Raised when connection to device access point fails."""
    pass 