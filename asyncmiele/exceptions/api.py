"""
API-related exceptions.
"""

from asyncmiele.exceptions import MieleException


class APIException(MieleException):
    """Exception raised for API-related errors."""
    pass


class DeviceNotFoundError(APIException):
    """Exception raised when a requested device is not found."""
    pass


class InvalidPathError(APIException):
    """Exception raised when an invalid API path is requested."""
    pass


class DecryptionError(APIException):
    """Exception raised when response decryption fails."""
    pass


class ParseError(APIException):
    """Exception raised when response parsing fails."""
    pass 