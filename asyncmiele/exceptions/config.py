"""
Exceptions related to device configuration and capabilities.
"""

from asyncmiele.exceptions import MieleException
from typing import Any


class ConfigurationError(MieleException):
    """Base class for all configuration-related exceptions."""
    pass


class UnsupportedCapabilityError(ConfigurationError):
    """Raised when attempting to use a capability not supported by the device."""
    pass


class DeviceConfigurationError(ConfigurationError):
    """Raised when there's an issue with the device configuration."""
    pass


class IncompatibleFirmwareError(ConfigurationError):
    """Raised when a device's firmware is incompatible with a requested operation."""
    pass


class ValidationError(ConfigurationError):
    """Raised when configuration validation fails."""
    pass


class InvalidConfigurationError(ConfigurationError):
    """Exception raised when configuration data is invalid."""
    
    def __init__(self, message: str, field: str = None, value: Any = None):
        super().__init__(message)
        self.field = field
        self.value = value


class CorruptedConfigurationError(ConfigurationError):
    """Exception raised when configuration file is corrupted or unreadable."""
    pass


class MissingConfigurationError(ConfigurationError):
    """Exception raised when required configuration is missing."""
    
    def __init__(self, message: str, missing_fields: list = None):
        super().__init__(message)
        self.missing_fields = missing_fields or []


class ConfigurationVersionError(ConfigurationError):
    """Exception raised when configuration version is incompatible."""
    
    def __init__(self, message: str, current_version: str = None, required_version: str = None):
        super().__init__(message)
        self.current_version = current_version
        self.required_version = required_version 