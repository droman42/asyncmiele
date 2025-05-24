"""
Async client for communicating with Miele devices.
"""

import json
import datetime
import binascii
from typing import Dict, Any, Optional, Union, Tuple, List, Set, Type, cast
from urllib.parse import quote

import aiohttp
import asyncio
import logging

from asyncmiele.exceptions.api import ParseError, DeviceNotFoundError
from asyncmiele.exceptions.network import (
    ResponseError,
    NetworkConnectionError,
    NetworkTimeoutError,
)
from asyncmiele.exceptions.auth import RegistrationError
from asyncmiele.exceptions.config import UnsupportedCapabilityError, ConfigurationError

from asyncmiele.models.response import MieleResponse
from asyncmiele.models.device import MieleDevice, DeviceIdentification, DeviceState
from asyncmiele.models.credentials import MieleCredentials
from asyncmiele.models.device_profile import DeviceProfile
from asyncmiele.enums import DeviceType

from asyncmiele.capabilities import DeviceCapability, detector, test_capability, detect_capabilities_as_sets

from asyncmiele.utils.crypto import generate_credentials, build_auth_header, pad_payload, encrypt_payload
import asyncmiele.utils.crypto as _crypto
from asyncmiele.dop2.models import SFValue, ConsumptionStats, DeviceGenerationType, DOP2Tree, DeviceCombinedState
from asyncmiele.dop2.explorer import DOP2Explorer
from asyncmiele.dop2.client import DOP2Client
from asyncmiele.dop2.visualizer import DOP2Visualizer, visualize_from_json
from asyncmiele.models.summary import DeviceSummary
from asyncmiele.utils.http_consts import ACCEPT_HEADER, USER_AGENT, CONTENT_TYPE_JSON

from asyncmiele.config import settings

logger = logging.getLogger(__name__)


class MieleClient:
    """Async client for communicating with Miele devices over the local API."""
    
    def __init__(
        self,
        host: str,
        group_id: bytes,
        group_key: bytes,
        timeout: float = 5.0,
        device_profile: Optional[DeviceProfile] = None
    ):
        """
        Initialize the Miele API client.
        
        Args:
            host: Host IP address or hostname
            group_id: GroupID in bytes (use bytes.fromhex() to convert from hex string)
            group_key: GroupKey in bytes (use bytes.fromhex() to convert from hex string)
            timeout: Timeout for API requests in seconds
            device_profile: Optional device profile for configuration and capability awareness
        """
        self.host = host
        self.group_id = group_id
        self.group_key = group_key
        self.timeout = timeout
        self.device_profile = device_profile
        
        # Initialize DOP2 protocol handler
        self._dop2 = DOP2Client()
        
        # Lazily-instantiated session (Phase-1 persistent connection pool)
        self._session: aiohttp.ClientSession | None = None
        
        # ------------------------------------------------------------------
        # Internal caches (Phase-4 helpers)
        # ------------------------------------------------------------------
        self._consumption_baseline: dict[str, tuple[datetime.date, ConsumptionStats]] = {}

    def _get_date_str(self) -> str:
        """Get a formatted date string for API requests."""
        return datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
        
    def _get_headers(self, date: Optional[str] = None, auth: Optional[str] = None) -> Dict[str, str]:
        """
        Get headers for API requests.
        
        Args:
            date: Optional date string (generated if not provided)
            auth: Optional authorization header value
            
        Returns:
            Dictionary of HTTP headers
        """
        if date is None:
            date = self._get_date_str()
            
        headers = {
            'Accept': ACCEPT_HEADER,
            'User-Agent': USER_AGENT,
            'Host': self.host,
            'Date': date,
        }
        
        if auth is not None:
            headers['Authorization'] = auth
            
        return headers
        
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

    # ------------------------------------------------------------------
    # Unified request implementation

    async def _request_bytes(
        self,
        method: str,
        resource: str,
        *,
        body: Optional[Union[bytes, str, Dict[str, Any]]] = None,
        allowed_status: tuple[int, ...] = (200,),
    ) -> tuple[int, bytes]:
        """Low-level request helper that handles signing, (en/de)cryption.

        Returns
        -------
        (status_code, decrypted_bytes)
        """

        method = method.upper()

        # ------------------------------------------------------------------
        # Prepare raw body bytes (before padding/encryption) – needed for HMAC.
        # ------------------------------------------------------------------
        if body is None:
            body_bytes: bytes = b""
        elif isinstance(body, bytes):
            body_bytes = body
        elif isinstance(body, str):
            body_bytes = body.encode("utf-8")
        else:  # assume JSON-serialisable
            body_bytes = json.dumps(body, separators=(",", ":")).encode()

        date_str = self._get_date_str()

        content_type_header = CONTENT_TYPE_JSON if method == "PUT" else ""

        # Build auth header + IV (IV only needed for PUT encryption)
        auth_header, iv = build_auth_header(
            method=method,
            host=self.host,
            resource=resource,
            date=date_str,
            group_id=self.group_id,
            group_key=self.group_key,
            content_type_header=content_type_header,
            body=body_bytes,
        )

        # Encrypt payload for PUT
        if method == "PUT":
            padded = pad_payload(body_bytes)
            key = self.group_key[: len(self.group_key) // 2]
            data_to_send = encrypt_payload(padded, key, iv) if padded else b""
        else:
            data_to_send = None  # GET has no body

        # ------------------------------------------------------------------
        # Build headers & fire request
        # ------------------------------------------------------------------
        headers = {
            "Accept": ACCEPT_HEADER,
            "User-Agent": USER_AGENT,
            "Host": self.host,
            "Date": date_str,
            "Authorization": auth_header,
        }
        if content_type_header:
            headers["Content-Type"] = content_type_header

        url = f"http://{self.host}{resource}"

        session = await self._get_session()

        try:
            async with session.request(
                method,
                url,
                data=data_to_send,
                headers=headers,
                timeout=self.timeout,
            ) as resp:

                if resp.status not in allowed_status:
                    raise ResponseError(resp.status, f"API error for {resource}")

                # 204 – No Content: nothing to decrypt/parse
                if resp.status == 204:
                    return resp.status, b""

                # Signature header is mandatory for encrypted responses
                if "X-Signature" not in resp.headers:
                    raise ResponseError(resp.status, "Missing X-Signature header in response")

                sig_hex = resp.headers["X-Signature"].split(":")[1]
                if len(sig_hex) % 2:
                    sig_hex = "0" + sig_hex
                sig_bytes = binascii.a2b_hex(sig_hex)

                encrypted_content = await resp.read()
                decrypted = _crypto.decrypt_response(encrypted_content, sig_bytes, self.group_key)

                return resp.status, decrypted

        except asyncio.TimeoutError as exc:
            raise NetworkTimeoutError(str(exc))
        except aiohttp.ClientConnectorError as exc:
            raise NetworkConnectionError(str(exc))
        except aiohttp.ClientError as exc:
            raise ResponseError(500, str(exc))

    async def _get_request(self, resource: str) -> MieleResponse:
        """
        Perform an authenticated GET request to the API.
        
        Args:
            resource: API resource path
            
        Returns:
            MieleResponse object containing the response data
            
        Raises:
            ConnectionError: If the connection fails
            TimeoutError: If the request times out
            ResponseError: If the server returns an error status
        """
        status, decrypted = await self._request_bytes("GET", resource, allowed_status=(200,))

        try:
            if decrypted:
                decoded = decrypted.decode("utf-8").strip()
                raw_data: Dict[str, Any] = json.loads(decoded) if decoded else {}
            else:
                raw_data = {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ParseError(f"Failed to parse response: {exc}")

        return MieleResponse(data=raw_data, root_path=resource)
        
    async def _put_request(self, resource: str, body: Optional[Union[bytes, str, Dict[str, Any]]] = None) -> Optional[MieleResponse]:
        """Send an authenticated PUT request (signed & encrypted).

        Parameters
        ----------
        resource
            Path starting with `/`.
        body
            Dict → JSON-serialised; ``str`` or ``bytes`` sent as-is.  ``None`` ⇒ empty body.

        Returns
        -------
        MieleResponse | None
            Parsed JSON if the device replied with 200 and content; ``None`` for 204/empty.
        """
        status, decrypted = await self._request_bytes(
            "PUT",
            resource,
            body=body,
            allowed_status=(200, 204),
        )

        if status == 204 or not decrypted:
            return None

        decoded = decrypted.decode("utf-8").strip()
        data_dict: Dict[str, Any] = json.loads(decoded) if decoded else {}
        return MieleResponse(data=data_dict, root_path=resource)
            
    async def get_devices(self) -> Dict[str, MieleDevice]:
        """
        Get all available devices.
        
        Returns:
            Dictionary mapping device IDs to MieleDevice objects
        """
        response = await self._get_request('/Devices/')
        devices = {}
        
        for device_id, device_data in response.data.items():
            # Create device with basic information
            device = MieleDevice(id=device_id)
            devices[device_id] = device
            
            # Load identification data if available
            if 'Ident' in device_data:
                ident_response = MieleResponse(
                    data=device_data['Ident'],
                    root_path=f'/Devices/{device_id}/Ident'
                )
                device.ident = DeviceIdentification.from_response(ident_response)
                
            # Load state data if available
            if 'State' in device_data:
                state_response = MieleResponse(
                    data=device_data['State'],
                    root_path=f'/Devices/{device_id}/State'
                )
                device.state = DeviceState.from_response(state_response)
                
        return devices
        
    async def get_device(self, device_id: str) -> MieleDevice:
        """
        Get a specific device by ID.
        
        Args:
            device_id: ID of the device to retrieve
            
        Returns:
            MieleDevice object
            
        Raises:
            DeviceNotFoundError: If the device is not found
        """
        devices = await self.get_devices()
        if device_id not in devices:
            raise DeviceNotFoundError(f"Device with ID {device_id} not found")
            
        return devices[device_id]
        
    async def get_device_state(self, device_id: str) -> DeviceState:
        """
        Get the current state of a specific device.
        
        Args:
            device_id: ID of the device to retrieve state for
            
        Returns:
            DeviceState object
            
        Raises:
            DeviceNotFoundError: If the device is not found
        """
        response = await self._get_request(f'/Devices/{quote(device_id, safe="")}/State')
        return DeviceState.from_response(response)
        
    async def get_device_ident(self, device_id: str) -> DeviceIdentification:
        """
        Get the identification information for a specific device.
        
        Args:
            device_id: ID of the device to retrieve identification for
            
        Returns:
            DeviceIdentification object
            
        Raises:
            DeviceNotFoundError: If the device is not found
        """
        response = await self._get_request(f'/Devices/{quote(device_id, safe="")}/Ident')
        return DeviceIdentification.from_response(response)
        
    async def register(self) -> bool:
        """
        Register this client with the Miele device.
        
        Returns:
            True if registration was successful
            
        Raises:
            RegistrationError: If registration fails
        """
        headers = self._get_headers()
        url = f'http://{self.host}/Security/Commissioning/'
        
        body = {
            'GroupID': self.group_id.hex(),
            'GroupKey': self.group_key.hex(),
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    url, 
                    json=body, 
                    headers=headers, 
                    timeout=self.timeout
                ) as response:
                    if response.status != 200:
                        raise RegistrationError(
                            response.status,
                            f"Registration failed with status {response.status}"
                        )
                    return True
                    
        except aiohttp.ClientError as e:
            raise RegistrationError(500, f"Registration failed: {str(e)}")
            
    @classmethod
    async def easy_setup(cls, host: str) -> Tuple[str, str, str]:
        """
        Create a new client and register it with a device.
        
        Args:
            host: Host IP address or hostname
            
        Returns:
            Tuple of (device_id, group_id, group_key)
            
        Raises:
            RegistrationError: If registration fails
        """
        group_id, group_key = generate_credentials()
        client = cls(
            host=host,
            group_id=bytes.fromhex(group_id),
            group_key=bytes.fromhex(group_key)
        )
        
        retry = 5
        while retry > 0:
            try:
                await client.register()
                devices = await client.get_devices()
                if devices:
                    device_id = list(devices.keys())[0]
                    return device_id, group_id, group_key
                retry -= 1
            except Exception:
                retry -= 1
                if retry <= 0:
                    raise
                
        raise RegistrationError(0, "Failed to register after multiple attempts")

    # ------------------------------------------------------------------
    # Phase-3 convenience constructors

    @classmethod
    def from_hex(
        cls,
        host: str,
        group_id_hex: str,
        group_key_hex: str,
        **kwargs,
    ) -> "MieleClient":
        """Instantiate a client from *hex* credential strings.

        Example
        -------
        >>> cli = MieleClient.from_hex(host, "aabbcc...", "112233...")
        """
        return cls(host, bytes.fromhex(group_id_hex), bytes.fromhex(group_key_hex), **kwargs)

    # ------------------------------------------------------------------
    # Batch summaries

    async def get_all_summaries(self) -> Dict[str, "DeviceSummary"]:
        """Fetch :pyclass:`DeviceSummary` for every known device in parallel."""
        devices = await self.get_devices()
        tasks = {dev_id: asyncio.create_task(self.get_summary(dev_id)) for dev_id in devices}
        results: Dict[str, DeviceSummary] = {}
        for dev_id, task in tasks.items():
            try:
                results[dev_id] = await task
            except Exception:
                # Skip failed device but keep others
                continue
        return results

    # ---------------------------------------------------------------------
    # Convenience helpers – Phase 3

    @test_capability(DeviceCapability.WAKE_UP)
    async def wake_up(self, device_id: str) -> None:
        """
        Wake up a device.
        
        This method sends a wake-up command to the device using DeviceAction: 2
        to match the MieleRESTServer reference implementation.
        
        Args:
            device_id: The ID of the device
        """
        body = {"DeviceAction": 2}
        await self._put_request(f"/Devices/{quote(device_id, safe='')}/State", body)
    
    @test_capability(DeviceCapability.REMOTE_START)
    async def can_remote_start(self, device_id: str) -> bool:
        """
        Check if a device can be remotely started.
        
        Based on MieleRESTServer reference implementation, this checks:
        - Status == 0x04 (device ready to start)
        - 15 in RemoteEnable (remote start capability enabled)
        
        Args:
            device_id: The ID of the device
            
        Returns:
            True if the device can be remotely started, False otherwise
        """
        try:
            # Get the device state to check status and remote enable flags
            state = await self.get_device_state(device_id)
            
            # Check if device is ready to start (Status == 0x04 = 4)
            device_ready = hasattr(state, 'status') and state.status == 4
            
            # Check if remote enable contains 15 (full remote control)
            remote_capable = False
            if hasattr(state, 'remote_enable') and state.remote_enable:
                remote_capable = 15 in state.remote_enable
            
            return device_ready and remote_capable
            
        except Exception:
            # If we can't get state, assume not ready
            return False
    
    @test_capability(DeviceCapability.REMOTE_START)
    async def remote_start(
        self, 
        device_id: str, 
        *, 
        allow_remote_start: Optional[bool] = None
    ) -> None:
        """
        Start a program remotely on the device.
        
        This method sends ProcessAction: 1 to start a program that has been
        prepared on the device, matching the MieleRESTServer reference implementation.
        
        Args:
            device_id: The ID of the device
            allow_remote_start: Whether to allow remote start (None to ignore, 
                              True to bypass settings check)
            
        Raises:
            PermissionError: If remote start is disabled and allow_remote_start is not True
        """
        # Check settings flag first for safety (unless explicitly allowed per call)
        if not settings.enable_remote_start and allow_remote_start is not True:
            raise PermissionError("Remote start disabled – see docs")
        
        # Check capability first
        self._require_capability(device_id, DeviceCapability.REMOTE_START)
        
        # Send the process action command to start the program
        body = {"ProcessAction": 1}
        await self._put_request(f"/Devices/{quote(device_id, safe='')}/State", body)
    
    @test_capability(DeviceCapability.PROGRAM_CATALOG)
    async def extract_program_catalog(self, device_id: str) -> Dict[str, Any]:
        """
        Extract the program catalog from a device.
        
        This method tries both the newer leaf method and the older method
        to maximize compatibility across different device models and firmware versions.
        
        Args:
            device_id: The ID of the device
            
        Returns:
            The program catalog
            
        Raises:
            UnsupportedCapabilityError: If the device does not support program catalogs
        """
        # Check capability first
        self._require_capability(device_id, DeviceCapability.PROGRAM_CATALOG)
        
        # Get the DOP2Client
        dop2_client = self.get_dop2_client()
        
        # Try to get the program catalog
        try:
            return await dop2_client.get_program_catalog(device_id)
        except Exception as e:
            logger.debug(f"Failed to get program catalog: {e}")
            raise UnsupportedCapabilityError(f"Device {device_id} does not support program catalogs")

    # ---------------------------------------------------------------------
    # Phase 10 – Settings helper via SF_Value (simplified)

    async def get_setting(self, device_id: str, sf_id: int) -> SFValue:
        """Get a setting value.
        
        Args:
            device_id: Device identifier
            sf_id: Setting ID
            
        Returns:
            SFValue object
        """
        parsed = await self.get_parsed_dop2_leaf(device_id, *self._dop2.LEAF_SF_VALUE, idx1=sf_id)
        if not isinstance(parsed, SFValue):
            raise ValueError("Leaf did not return SFValue structure")
        return parsed

    async def set_setting(self, device_id: str, sf_id: int, new_value: int) -> None:
        """Set a setting value.
        
        Args:
            device_id: Device identifier
            sf_id: Setting ID
            new_value: New value to set
        """
        sf = await self.get_setting(device_id, sf_id)
        
        if not (sf.minimum <= new_value <= sf.maximum):
            raise ValueError(f"Value {new_value} outside allowed range {sf.minimum}-{sf.maximum}")
        
        payload = self._dop2.build_sf_value_payload(sf_id, new_value)
        await self.write_dop2_leaf(device_id, *self._dop2.LEAF_SF_VALUE, payload, idx1=sf_id)

    # ---------------------------------------------------------------------
    # Phase 11 – Summary helper

    async def get_summary(self, device_id: str) -> DeviceSummary:
        """Return a consolidated overview for *device_id*."""
        ident_task = asyncio.create_task(self.get_device_ident(device_id))
        state_task = asyncio.create_task(self.get_device_state(device_id))

        combined_state_task = asyncio.create_task(
            self.get_parsed_dop2_leaf(device_id, 2, 256)
        )

        ready_task = asyncio.create_task(self.can_remote_start(device_id))

        ident = await ident_task
        state = await state_task

        combined = None
        try:
            parsed = await combined_state_task

            if isinstance(parsed, DeviceCombinedState):
                combined = parsed
        except Exception:
            pass  # leaf may be absent

        # progress calculation
        progress = None
        if state.remaining_time and state.elapsed_time is not None:
            try:
                total = state.remaining_time + state.elapsed_time
                if total > 0:
                    progress = state.elapsed_time / total
            except Exception:
                pass

        ready = await ready_task

        return DeviceSummary(
            id=device_id,
            name=ident.device_name or ident.tech_type,
            ident=ident,
            state=state,
            combined_state=combined,
            progress=progress,
            ready_to_start=ready,
        )

    # ---------------------------------------------------------------------
    # Phase 15 – Consumption statistics helper

    # ---------------------------------------------------------------------
    # Program catalog extraction methods

    # ------------------------------------------------------------------
    # Device capability methods
    # ------------------------------------------------------------------
    
    def _require_capability(self, device_id: str, capability: DeviceCapability) -> None:
        """
        Check if a device has a specific capability, raising an exception if not.
        
        Args:
            device_id: The ID of the device
            capability: The capability to check
            
        Raises:
            UnsupportedCapabilityError: If the device does not have the capability
        """
        # If we have a device profile, check its capabilities
        if self.device_profile and self.device_profile.device_id == device_id:
            if not self.device_profile.has_capability(capability):
                raise UnsupportedCapabilityError(
                    f"Device {device_id} does not support the {capability.name} capability"
                )
        # Otherwise, check the global capability detector
        elif not detector.has_capability(device_id, capability):
            raise UnsupportedCapabilityError(
                f"Device {device_id} does not support the {capability.name} capability"
            )
    
    async def detect_capabilities(self, device_id: str) -> DeviceCapability:
        """Detect device capabilities using systematic testing.
        
        Returns:
            Detected capabilities as IntFlag
        """
        # Get device to determine type
        device = await self.get_device(device_id)
        device_type = device.ident.type_id if device.ident else DeviceType.NoUse
        
        # Run capability tests
        detected = DeviceCapability.NONE
        
        # Test basic capabilities
        try:
            await self.get_device_state(device_id)
            detected |= DeviceCapability.STATE_REPORTING
            detector.record_capability_test(device_id, DeviceCapability.STATE_REPORTING, True)
        except Exception:
            detector.record_capability_test(device_id, DeviceCapability.STATE_REPORTING, False)
        
        try:
            await self.wake_up(device_id)
            detected |= DeviceCapability.WAKE_UP
            detector.record_capability_test(device_id, DeviceCapability.WAKE_UP, True)
        except Exception:
            detector.record_capability_test(device_id, DeviceCapability.WAKE_UP, False)
        
        try:
            can_start = await self.can_remote_start(device_id)
            if can_start:
                detected |= DeviceCapability.REMOTE_START
            detector.record_capability_test(device_id, DeviceCapability.REMOTE_START, can_start)
        except Exception:
            detector.record_capability_test(device_id, DeviceCapability.REMOTE_START, False)
        
        try:
            catalog = await self.get_program_catalog(device_id)
            if catalog and len(catalog.get("programs", {})) > 0:
                detected |= DeviceCapability.PROGRAM_CATALOG
            detector.record_capability_test(device_id, DeviceCapability.PROGRAM_CATALOG, True)
        except Exception:
            detector.record_capability_test(device_id, DeviceCapability.PROGRAM_CATALOG, False)
        
        return detected
    
    async def detect_capabilities_as_sets(self, device_id: str) -> Tuple[Set[DeviceCapability], Set[DeviceCapability]]:
        """Detect device capabilities and return as sets (Phase 3 enhancement).
        
        This is the preferred method for new code using the enhanced configuration system.
        Returns (supported_capabilities, failed_capabilities) as sets for DeviceProfile.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Tuple of (supported_capabilities, failed_capabilities) as sets
        """
        # Get device to determine type
        try:
            device = await self.get_device(device_id)
            device_type = device.ident.type_id if device.ident else DeviceType.NoUse
        except Exception:
            device_type = DeviceType.NoUse
        
        # Use the enhanced set-based detection function
        return await detect_capabilities_as_sets(self, device_id, device_type)

    # ------------------------------------------------------------------
    # Factory methods for configuration support
    # ------------------------------------------------------------------
    
    @classmethod
    def from_profile(cls, profile: DeviceProfile) -> "MieleClient":
        """
        Create a client from a device profile.
        
        Args:
            profile: The device profile with direct connection fields
            
        Returns:
            A new MieleClient instance
        """
        client = cls(
            host=profile.host,                    # Direct access - no config wrapper
            group_id=profile.credentials.group_id,
            group_key=profile.credentials.group_key,
            timeout=profile.timeout,              # Direct access from DeviceProfile
            device_profile=profile
        )
        return client

    async def detect_device_generation(self, device_id: str) -> DeviceGenerationType:
        """Detect the generation of a Miele device.
        
        This method probes common DOP2 leaves to determine which generation
        the device belongs to based on successful leaf access.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Detected device generation type
        """
        # If we already have leaves registered, use those
        generation = self._dop2.detect_generation_from_leaves(device_id)
        if generation != DeviceGenerationType.UNKNOWN:
            return generation
        
        # Otherwise, try to probe some common leaves to determine generation
        try:
            # Try DOP2 leaf
            await self.read_dop2_leaf(device_id, *self._dop2.LEAF_COMBINED_STATE)
        except Exception:
            pass
        
        try:
            # Try legacy leaf
            await self.read_dop2_leaf(device_id, *self._dop2.LEAF_LEGACY_PROGRAM_LIST)
        except Exception:
            pass
        
        try:
            # Try semipro leaf
            await self.read_dop2_leaf(device_id, *self._dop2.LEAF_SEMIPRO_CONFIG)
        except Exception:
            pass
        
        # Now detect based on what succeeded
        return self._dop2.detect_generation_from_leaves(device_id)

    # ------------------------------------------------------------------
    # DOP2 HTTP communication methods (replacing DOP2Client HTTP functionality)
    # ------------------------------------------------------------------
    
    async def read_dop2_leaf(self, device_id: str, unit: int, attribute: int, 
                           idx1: int = 0, idx2: int = 0) -> bytes:
        """Read raw data from a DOP2 leaf.
        
        Args:
            device_id: Device identifier
            unit: DOP2 unit number
            attribute: DOP2 attribute number
            idx1: First index parameter
            idx2: Second index parameter
            
        Returns:
            Raw binary data from the leaf
        """
        path = self._dop2.build_leaf_path(device_id, unit, attribute, idx1, idx2)
        response = await self._get_request(path)
        
        # Register successful leaf access with generation detector
        self._dop2.register_successful_leaf(device_id, unit, attribute)
        
        # Extract raw data from response
        if hasattr(response, 'raw_data'):
            return response.raw_data
        elif hasattr(response, 'data') and isinstance(response.data, bytes):
            return response.data
        else:
            # Convert response to bytes if needed
            import json
            return json.dumps(response.data).encode('utf-8')

    async def write_dop2_leaf(self, device_id: str, unit: int, attribute: int, 
                            payload: bytes, idx1: int = 0, idx2: int = 0) -> None:
        """Write data to a DOP2 leaf.
        
        Args:
            device_id: Device identifier
            unit: DOP2 unit number
            attribute: DOP2 attribute number
            payload: Binary data to write
            idx1: First index parameter
            idx2: Second index parameter
        """
        path = self._dop2.build_leaf_path(device_id, unit, attribute, idx1, idx2)
        await self._put_request(path, payload)
        
        # Register successful leaf access with generation detector
        self._dop2.register_successful_leaf(device_id, unit, attribute)

    async def get_parsed_dop2_leaf(self, device_id: str, unit: int, attribute: int,
                                 idx1: int = 0, idx2: int = 0) -> Union[Dict[str, Any], List[Any], str, int, float, bytes]:
        """Get parsed data from a DOP2 leaf.
        
        Args:
            device_id: Device identifier
            unit: DOP2 unit number
            attribute: DOP2 attribute number
            idx1: First index parameter
            idx2: Second index parameter
            
        Returns:
            Parsed leaf data (type depends on the specific leaf)
        """
        raw_data = await self.read_dop2_leaf(device_id, unit, attribute, idx1=idx1, idx2=idx2)
        return self._dop2.parse_leaf_response(unit, attribute, raw_data)

    async def get_program_catalog(self, device_id: str) -> Dict[str, Any]:
        """Extract program catalog data using correct DOP2 leaves.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Program catalog dictionary
        """
        # Try the primary method first
        try:
            return await self._get_program_catalog_primary(device_id)
        except Exception as e:
            logger.debug(f"Failed to get program catalog using primary method: {e}")
            # Fall back to legacy method
            return await self._get_program_catalog_legacy(device_id)

    async def _get_program_catalog_primary(self, device_id: str) -> Dict[str, Any]:
        """Extract program catalog using leaf 2/1584.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Program catalog dictionary
        """
        # First get the program IDs from the correct leaf
        program_list_data = await self.get_parsed_dop2_leaf(device_id, *self._dop2.LEAF_PROGRAM_LIST)
        
        # Get device info for the device type
        ident = await self.get_device_ident(device_id)
        if isinstance(ident.device_type, int):
            try:
                device_type = DeviceType(ident.device_type).name
            except ValueError:
                device_type = f"unknown_{ident.device_type}"
        else:
            device_type = ident.device_type or ident.tech_type or "unknown"
        
        return self._dop2.parse_program_catalog_primary(program_list_data, device_type)

    async def _get_program_catalog_legacy(self, device_id: str) -> Dict[str, Any]:
        """Extract program catalog using legacy leaves 14/1570, 14/1571, and 14/2570.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Program catalog dictionary
        """
        try:
            # Get program list
            program_list = await self.get_parsed_dop2_leaf(device_id, *self._dop2.LEAF_LEGACY_PROGRAM_LIST)
            
            # Get option lists for each program
            option_lists = {}
            if hasattr(program_list, 'programs'):
                for prog_entry in program_list.programs:
                    try:
                        option_list = await self.get_parsed_dop2_leaf(
                            device_id, *self._dop2.LEAF_LEGACY_OPTION_LIST, idx1=prog_entry.program_id
                        )
                        option_lists[prog_entry.program_id] = option_list
                    except Exception:
                        pass  # Continue if we can't get options for this program
            
            # Get string table
            string_table = {}
            try:
                string_table = await self.get_parsed_dop2_leaf(device_id, *self._dop2.LEAF_LEGACY_STRING_TABLE)
            except Exception:
                pass  # Continue with empty string table
            
            # Get device type
            ident = await self.get_device_ident(device_id)
            if isinstance(ident.device_type, int):
                try:
                    device_type = DeviceType(ident.device_type).name
                except ValueError:
                    device_type = f"unknown_{ident.device_type}"
            else:
                device_type = ident.device_type or ident.tech_type or "unknown"
            
            return self._dop2.parse_program_catalog_legacy(program_list, option_lists, string_table, device_type)
            
        except Exception as e:
            logger.debug(f"Failed to get program catalog using legacy method: {e}")
            # If the old way fails, return empty catalog
            return {"device_type": "unknown", "programs": []}

    async def get_consumption_stats(self, device_id: str) -> ConsumptionStats:
        """Get consumption statistics for a device.
        
        This method orchestrates multiple DOP2 leaf reads to build comprehensive
        consumption statistics.
        
        Args:
            device_id: Device identifier
            
        Returns:
            ConsumptionStats object with available data
        """
        hours_data = None
        cycles_data = None
        process_data = None
        
        try:
            hours_data = await self.get_parsed_dop2_leaf(device_id, *self._dop2.LEAF_HOURS_OF_OPERATION)
        except Exception:
            pass
        
        try:
            cycles_data = await self.get_parsed_dop2_leaf(device_id, *self._dop2.LEAF_CYCLE_COUNTER)
        except Exception:
            pass
        
        try:
            process_data = await self.get_parsed_dop2_leaf(device_id, *self._dop2.LEAF_CONSUMPTION_STATS)
        except Exception:
            pass
        
        return self._dop2.build_consumption_stats(hours_data, cycles_data, process_data)

    def get_dop2_client(self) -> DOP2Client:
        """Get a DOP2Client instance configured with this client.
        
        Returns:
            DOP2Client instance
        """
        return DOP2Client(self)

    # Note: The get_dop2_client() method is kept for backward compatibility.
    # All DOP2 operations are now handled directly by MieleClient HTTP methods.
    # 
    # MieleClient implements the DOP2LeafReader protocol, so it can be used
    # directly with DOP2Explorer for clean dependency inversion.
    
    def create_dop2_explorer(self) -> "DOP2Explorer":
        """Create a DOP2Explorer instance using this client as a data provider.
        
        This uses the data provider pattern - DOP2Explorer gets a simple function
        for reading leaf data while keeping all DOP2 protocol knowledge internal.
        
        Returns:
            DOP2Explorer instance configured to use this client
        """
        from asyncmiele.dop2.explorer import DOP2Explorer
        
        # Create a simple data provider function
        async def data_provider(device_id: str, unit: int, attribute: int, idx1: int = 0, idx2: int = 0):
            return await self.get_parsed_dop2_leaf(device_id, unit, attribute, idx1, idx2)
        
        return DOP2Explorer(data_provider)
