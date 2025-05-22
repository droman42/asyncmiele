"""
Async client for setting up and provisioning Miele devices.

This module provides the MieleSetupClient class for initial setup of Miele devices,
including WiFi configuration and security credential provisioning.
"""

import json
import asyncio
import logging
from typing import Dict, Any, Optional, Union, Tuple, List

import aiohttp

from asyncmiele.models.credentials import MieleCredentials
from asyncmiele.models.network_config import MieleNetworkConfig
from asyncmiele.exceptions.network import ResponseError, NetworkConnectionError, NetworkTimeoutError
from asyncmiele.exceptions.setup import SetupError, WifiConfigurationError, ProvisioningError

logger = logging.getLogger(__name__)

# Constants for setup
WIFI_SETUP_ENDPOINT = "/WLAN"
SECURITY_SETUP_ENDPOINT = "/Security/Commissioning"
DEFAULT_AP_HOST = "192.168.1.1"  # Default IP when device is in access point mode
DEFAULT_TIMEOUT = 5.0
DEFAULT_USER_AGENT = "Miele@mobile 2.3.3 iOS"


class MieleSetupClient:
    """
    Async client for setting up and provisioning Miele devices.
    
    This client is used for the initial setup of a Miele device, including:
    - WiFi configuration
    - Security credentials provisioning
    
    Unlike MieleClient, this client does not require authentication as it's
    designed to work with devices in setup mode.
    """
    
    def __init__(
        self,
        host: str = DEFAULT_AP_HOST,
        timeout: float = DEFAULT_TIMEOUT
    ):
        """
        Initialize the Miele setup client.
        
        Args:
            host: Host IP address or hostname of the device in setup mode
                 (default: 192.168.1.1 - typical AP mode address)
            timeout: Timeout for API requests in seconds
        """
        self.host = host
        self.timeout = timeout
        
        # Lazily-instantiated session
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Return an open *aiohttp* session, creating it on first use."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the underlying *aiohttp* session (idempotent)."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    # Async-context manager convenience
    async def __aenter__(self):
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        body: Optional[Union[bytes, str, Dict[str, Any]]] = None,
        use_https: bool = False,
        allowed_status: Tuple[int, ...] = (200, 204),
    ) -> Tuple[int, bytes]:
        """
        Send a request to the device.
        
        Args:
            method: HTTP method (GET, PUT, etc.)
            endpoint: API endpoint
            body: Request body
            use_https: Whether to use HTTPS instead of HTTP
            allowed_status: Status codes that are considered successful
            
        Returns:
            Tuple of (status_code, response_bytes)
            
        Raises:
            ResponseError: If the response status is not in allowed_status
            NetworkConnectionError: If the connection fails
            NetworkTimeoutError: If the request times out
        """
        method = method.upper()
        
        # Prepare body
        if body is None:
            body_data = None
        elif isinstance(body, bytes):
            body_data = body
        elif isinstance(body, str):
            body_data = body.encode("utf-8")
        else:  # JSON-serializable object
            body_data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        
        # Build URL
        scheme = "https" if use_https else "http"
        url = f"{scheme}://{self.host}{endpoint}"
        
        # Prepare headers
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Host": self.host,
        }
        
        if body is not None and not isinstance(body, bytes):
            headers["Content-Type"] = "application/json"
        
        session = await self._get_session()
        
        try:
            async with session.request(
                method,
                url,
                data=body_data,
                headers=headers,
                timeout=self.timeout,
                ssl=False,  # Skip SSL verification for self-signed certs
            ) as resp:
                if resp.status not in allowed_status:
                    raise ResponseError(resp.status, f"API error for {endpoint}: {resp.reason}")
                
                # Read response body
                response_bytes = await resp.read()
                return resp.status, response_bytes
                
        except aiohttp.ClientConnectorError as e:
            raise NetworkConnectionError(f"Failed to connect to {self.host}: {str(e)}")
        except asyncio.TimeoutError:
            raise NetworkTimeoutError(f"Request to {self.host} timed out after {self.timeout} seconds")
    
    async def configure_wifi(
        self,
        network_config: MieleNetworkConfig,
        *,
        use_https: bool = False,
        retry_count: int = 2,
    ) -> bool:
        """
        Configure the WiFi settings of a device in setup mode.
        
        Args:
            network_config: WiFi network configuration
            use_https: Whether to use HTTPS instead of HTTP
            retry_count: Number of retries on failure
            
        Returns:
            True if configuration was successful
            
        Raises:
            WifiConfigurationError: If the configuration fails
        """
        logger.info(f"Configuring WiFi for device at {self.host}")
        
        # Try the request, with retries
        for attempt in range(retry_count + 1):
            try:
                # Send the network configuration to the device
                status, response = await self._request(
                    method="PUT",
                    endpoint=WIFI_SETUP_ENDPOINT,
                    body=network_config.model_dump(),
                    use_https=use_https,
                    allowed_status=(200, 202, 204),
                )
                
                logger.info(f"WiFi configuration successful with status {status}")
                return True
                
            except (ResponseError, NetworkConnectionError, NetworkTimeoutError) as e:
                logger.warning(f"WiFi configuration attempt {attempt+1} failed: {str(e)}")
                
                if attempt < retry_count:
                    # Wait a bit before retrying
                    await asyncio.sleep(1)
                else:
                    raise WifiConfigurationError(f"Failed to configure WiFi after {retry_count+1} attempts") from e
        
        # Should never reach here but just to be safe
        return False
    
    async def provision_credentials(
        self,
        host: str,
        credentials: MieleCredentials,
        *,
        use_https: bool = False,
        try_both_protocols: bool = True,
        retry_count: int = 2,
    ) -> bool:
        """
        Provision security credentials to a device.
        
        Args:
            host: Host IP address or hostname of the device (not in setup mode)
            credentials: Security credentials to provision
            use_https: Whether to use HTTPS instead of HTTP
            try_both_protocols: Whether to try both HTTP and HTTPS if the first fails
            retry_count: Number of retries on failure
            
        Returns:
            True if provisioning was successful
            
        Raises:
            ProvisioningError: If the provisioning fails
        """
        logger.info(f"Provisioning security credentials to device at {host}")
        
        # Store original host and restore it after the operation
        original_host = self.host
        self.host = host
        
        try:
            # Try the selected protocol first
            success = await self._try_provision_credentials(
                credentials=credentials,
                use_https=use_https,
                retry_count=retry_count,
            )
            
            # If the first attempt failed and we're allowed to try both protocols, try the other one
            if not success and try_both_protocols:
                logger.info(f"Trying alternative protocol for provisioning")
                success = await self._try_provision_credentials(
                    credentials=credentials,
                    use_https=not use_https,
                    retry_count=retry_count,
                )
            
            if not success:
                raise ProvisioningError(f"Failed to provision credentials to {host}")
            
            return success
            
        finally:
            # Restore original host
            self.host = original_host
    
    async def _try_provision_credentials(
        self,
        credentials: MieleCredentials,
        *,
        use_https: bool = False,
        retry_count: int = 2,
    ) -> bool:
        """
        Internal helper to try provisioning credentials with a specific protocol.
        
        Args:
            credentials: Security credentials to provision
            use_https: Whether to use HTTPS instead of HTTP
            retry_count: Number of retries on failure
            
        Returns:
            True if provisioning was successful, False otherwise
        """
        protocol = "HTTPS" if use_https else "HTTP"
        logger.info(f"Trying {protocol} for credential provisioning")
        
        # Prepare credentials in the format expected by the device
        creds_data = {
            "GroupID": credentials.get_id_hex(),
            "GroupKey": credentials.get_key_hex(),
        }
        
        # Try the request, with retries
        for attempt in range(retry_count + 1):
            try:
                # Send the credentials to the device
                status, response = await self._request(
                    method="PUT",
                    endpoint=SECURITY_SETUP_ENDPOINT,
                    body=creds_data,
                    use_https=use_https,
                    allowed_status=(200, 202, 204),
                )
                
                logger.info(f"Credential provisioning successful with status {status} using {protocol}")
                return True
                
            except (ResponseError, NetworkConnectionError, NetworkTimeoutError) as e:
                logger.warning(f"Credential provisioning attempt {attempt+1} failed with {protocol}: {str(e)}")
                
                if attempt < retry_count:
                    # Wait a bit before retrying
                    await asyncio.sleep(1)
        
        logger.error(f"All provisioning attempts with {protocol} failed")
        return False 