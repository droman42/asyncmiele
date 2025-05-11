"""
Network-related exceptions.
"""

from asyncmiele.exceptions import MieleException


class NetworkException(MieleException):
    """Exception raised for network-related errors."""
    pass


class ConnectionError(NetworkException):
    """Exception raised when a connection to a Miele device cannot be established."""
    pass


class TimeoutError(NetworkException):
    """Exception raised when a request to a Miele device times out."""
    pass


class ResponseError(NetworkException):
    """Exception raised when a response from a Miele device indicates an error."""
    
    def __init__(self, status_code, message=None):
        """Initialize the exception with a status code and optional message.
        
        Args:
            status_code: HTTP status code
            message: Optional error message
        """
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP error {status_code}{': ' + message if message else ''}") 