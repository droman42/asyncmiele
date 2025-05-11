"""
Authentication-related exceptions.
"""

from asyncmiele.exceptions import MieleException


class AuthenticationException(MieleException):
    """Exception raised for authentication-related errors."""
    pass


class InvalidCredentialsError(AuthenticationException):
    """Exception raised when the provided GroupID or GroupKey are invalid."""
    pass


class AuthorizationError(AuthenticationException):
    """Exception raised when the client is not authorized to access a resource."""
    pass


class RegistrationError(AuthenticationException):
    """Exception raised when device registration fails."""
    
    def __init__(self, status_code, message=None):
        """Initialize the exception with a status code and optional message.
        
        Args:
            status_code: HTTP status code
            message: Optional error message
        """
        self.status_code = status_code
        self.message = message
        super().__init__(f"Registration failed with code {status_code}{': ' + message if message else ''}") 