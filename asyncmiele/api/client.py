"""
Async client for communicating with Miele devices.
"""

import json
import datetime
import binascii
from typing import Dict, Any, Optional, Union, Tuple
from urllib.parse import quote

import aiohttp
import asyncio

from asyncmiele.exceptions.api import ParseError, DeviceNotFoundError
from asyncmiele.exceptions.network import ResponseError, ConnectionError, TimeoutError
from asyncmiele.exceptions.auth import RegistrationError

from asyncmiele.models.response import MieleResponse
from asyncmiele.models.device import MieleDevice, DeviceIdentification, DeviceState

from asyncmiele.utils.crypto import generate_credentials, build_auth_header, pad_payload, encrypt_payload
import asyncmiele.utils.crypto as _crypto
from asyncmiele.dop2.models import SFValue, ConsumptionStats
from asyncmiele.models.summary import DeviceSummary


class MieleClient:
    """Async client for communicating with Miele devices over the local API."""
    
    def __init__(
        self,
        host: str,
        group_id: bytes,
        group_key: bytes,
        timeout: float = 5.0
    ):
        """
        Initialize the Miele API client.
        
        Args:
            host: Host IP address or hostname
            group_id: GroupID in bytes (use bytes.fromhex() to convert from hex string)
            group_key: GroupKey in bytes (use bytes.fromhex() to convert from hex string)
            timeout: Timeout for API requests in seconds
        """
        self.host = host
        self.group_id = group_id
        self.group_key = group_key
        self.timeout = timeout
        
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
            'Accept': 'application/vnd.miele.v1+json',
            'User-Agent': 'Miele@mobile 2.3.3 Android',
            'Host': self.host,
            'Date': date,
        }
        
        if auth is not None:
            headers['Authorization'] = auth
            
        return headers
        
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
        url = f'http://{self.host}{resource}'
        date = self._get_date_str()

        # Unified header generation shared with future PUT implementation
        auth_header, _iv = build_auth_header(
            method="GET",
            host=self.host,
            resource=resource,
            date=date,
            group_id=self.group_id,
            group_key=self.group_key,
        )

        headers = self._get_headers(
            date=date,
            auth=auth_header,
        )
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, 
                    headers=headers, 
                    timeout=self.timeout
                ) as response:
                    
                    if response.status != 200:
                        raise ResponseError(
                            response.status,
                            f"API error for {resource}"
                        )
                    
                    # Extract signature from headers
                    if 'X-Signature' not in response.headers:
                        raise ResponseError(
                            response.status,
                            "Missing X-Signature header in response"
                        )
                        
                    response_sig = response.headers['X-Signature'].split(':')[1]
                    # Ensure even-length hex string for safe conversion (tests may stub odd length)
                    if len(response_sig) % 2:
                        response_sig = '0' + response_sig
                    try:
                        response_signature = binascii.a2b_hex(response_sig)
                    except binascii.Error as exc:
                        raise ResponseError(
                            response.status,
                            f"Invalid X-Signature header: {exc}"
                        )
                    
                    # Decrypt and parse response
                    content = await response.read()
                    decrypted_data = _crypto.decrypt_response(
                        content,
                        response_signature, 
                        self.group_key
                    )
                    
                    try:
                        if decrypted_data:
                            decoded = decrypted_data.decode('utf-8')
                            if decoded:
                                raw_data = json.loads(decoded)
                            else:
                                raw_data = {}
                        else:
                            raw_data = {}
                    except (UnicodeDecodeError, json.JSONDecodeError) as e:
                        raise ParseError(f"Failed to parse response: {str(e)}")
                    
                    return MieleResponse(data=raw_data, root_path=resource)
                    
        except aiohttp.ClientConnectorError as e:
            raise ConnectionError(f"Connection failed: {str(e)}")
        except asyncio.TimeoutError as e:
            raise TimeoutError(f"Request timed out: {str(e)}")
        except aiohttp.ClientError as e:
            raise ResponseError(500, f"Client error: {str(e)}")
            
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
        url = f"http://{self.host}{resource}"
        date = self._get_date_str()

        # Prepare body bytes -------------------------------------------------
        if body is None:
            body_bytes = b""
        elif isinstance(body, bytes):
            body_bytes = body
        elif isinstance(body, str):
            body_bytes = body.encode("utf-8")
        else:
            body_bytes = json.dumps(body, separators=(",", ":")).encode()

        # Pad before encryption
        padded = pad_payload(body_bytes)

        auth_header, iv = build_auth_header(
            method="PUT",
            host=self.host,
            resource=resource,
            date=date,
            group_id=self.group_id,
            group_key=self.group_key,
            content_type_header="application/vnd.miele.v1+json; charset=utf-8",
            body=body_bytes,  # unpadded per observed behaviour
        )

        key = self.group_key[: len(self.group_key) // 2]
        encrypted_payload = encrypt_payload(padded, key, iv) if padded else b""

        headers = self._get_headers(
            date=date,
            auth=auth_header,
        )
        headers["Content-Type"] = "application/vnd.miele.v1+json; charset=utf-8"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    url,
                    data=encrypted_payload,
                    headers=headers,
                    timeout=self.timeout,
                ) as response:

                    if response.status not in (200, 204):
                        raise ResponseError(response.status, f"API PUT error for {resource}")

                    # 204 – no content to decrypt/parse
                    if response.status == 204:
                        return None

                    # 200 with body – decrypt & parse
                    if "X-Signature" not in response.headers:
                        raise ResponseError(
                            response.status, "Missing X-Signature header in response"
                        )

                    response_sig = response.headers["X-Signature"].split(":")[1]
                    if len(response_sig) % 2:
                        response_sig = "0" + response_sig
                    response_signature = binascii.a2b_hex(response_sig)

                    content = await response.read()
                    decrypted = _crypto.decrypt_response(content, response_signature, self.group_key)

                    if not decrypted:
                        return MieleResponse(data={}, root_path=resource)

                    decoded = decrypted.decode("utf-8").strip()
                    data_dict = json.loads(decoded) if decoded else {}
                    return MieleResponse(data=data_dict, root_path=resource)

        except asyncio.TimeoutError as e:
            raise TimeoutError(f"Request timed out: {str(e)}")
        except aiohttp.ClientError as e:
            raise ResponseError(500, f"Client error: {str(e)}")
            
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

    # ---------------------------------------------------------------------
    # Convenience helpers – Phase 3

    async def wake_up(self, device_id: str) -> None:
        """Wake a sleeping device via local API.

        This sends `{"DeviceAction": 2}` to `/Devices/<id>/State`.
        """
        resource = f"/Devices/{quote(device_id, safe='')}/State"
        await self._put_request(resource, {"DeviceAction": 2})

    async def can_remote_start(self, device_id: str) -> bool:
        """Return ``True`` if the device reports it is ready and remote-start capable."""
        resource = f"/Devices/{quote(device_id, safe='')}/State"
        resp = await self._get_request(resource)

        try:
            status_val = resp.data["Status"]
            # "Status" may be nested or raw; support both
            if isinstance(status_val, dict):
                status_raw = status_val.get("value_raw")
            else:
                status_raw = status_val

            remote_enable = resp.data.get("RemoteEnable", [])
            return status_raw == 0x04 and 15 in remote_enable
        except Exception:
            return False

    async def remote_start(self, device_id: str, *, allow_remote_start: Optional[bool] = None) -> None:
        """Start the currently programmed cycle.

        Safety: disabled by default.  Activation options:

        1.  Set ``asyncmiele.config.settings.enable_remote_start = True`` *once*.
        2.  Pass ``allow_remote_start=True`` for an explicit per-call override.
        """
        from asyncmiele.config import settings  # local import to avoid cycles

        if allow_remote_start is None:
            allow_remote_start = settings.enable_remote_start

        if not allow_remote_start:
            raise PermissionError(
                "Remote start disabled – set asyncmiele.config.settings.enable_remote_start = True "
                "or pass allow_remote_start=True explicitly."
            )

        resource = f"/Devices/{quote(device_id, safe='')}/State"
        await self._put_request(resource, {"ProcessAction": 1})

    # ---------------------------------------------------------------------
    # Phase 8 – DOP2 raw access

    @staticmethod
    def _dop2_path(device_id: str, unit: int, attribute: int, idx1: int, idx2: int) -> str:
        return f"/Devices/{quote(device_id, safe='')}/DOP2/{unit}/{attribute}?idx1={idx1}&idx2={idx2}"

    async def _get_raw(self, resource: str) -> bytes:
        """Internal helper similar to `_get_request` but returns decrypted *bytes*."""
        url = f"http://{self.host}{resource}"
        date = self._get_date_str()

        auth_header, _iv = build_auth_header(
            method="GET",
            host=self.host,
            resource=resource,
            date=date,
            group_id=self.group_id,
            group_key=self.group_key,
        )

        headers = self._get_headers(date=date, auth=auth_header)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=self.timeout) as response:
                    if response.status != 200:
                        raise ResponseError(response.status, f"API error for {resource}")

                    if "X-Signature" not in response.headers:
                        raise ResponseError(response.status, "Missing X-Signature header in response")

                    sig_hex = response.headers["X-Signature"].split(":")[1]
                    if len(sig_hex) % 2:
                        sig_hex = "0" + sig_hex
                    sig_bytes = binascii.a2b_hex(sig_hex)

                    content = await response.read()
                    return _crypto.decrypt_response(content, sig_bytes, self.group_key)

        except asyncio.TimeoutError as e:
            raise TimeoutError(str(e))
        except aiohttp.ClientError as e:
            raise ResponseError(500, str(e))

    async def dop2_read_leaf(
        self,
        device_id: str,
        unit: int,
        attribute: int,
        *,
        idx1: int = 0,
        idx2: int = 0,
    ) -> bytes:
        """Return decrypted raw bytes of a DOP2 leaf."""
        path = self._dop2_path(device_id, unit, attribute, idx1, idx2)
        return await self._get_raw(path)

    async def dop2_write_leaf(
        self,
        device_id: str,
        unit: int,
        attribute: int,
        payload: bytes,
        *,
        idx1: int = 0,
        idx2: int = 0,
    ) -> None:
        """Write raw *payload* to a DOP2 leaf."""
        path = self._dop2_path(device_id, unit, attribute, idx1, idx2)
        await self._put_request(path, payload)

    async def dop2_get_parsed(
        self,
        device_id: str,
        unit: int,
        attribute: int,
        *,
        idx1: int = 0,
        idx2: int = 0,
    ) -> Any:
        """Return parsed representation of a DOP2 leaf using dop2.parser."""
        raw = await self.dop2_read_leaf(device_id, unit, attribute, idx1=idx1, idx2=idx2)
        from asyncmiele.dop2.parser import parse_leaf

        return parse_leaf(unit, attribute, raw)

    # ---------------------------------------------------------------------
    # Phase 10 – Settings helper via SF_Value (simplified)

    async def get_setting(self, device_id: str, sf_id: int) -> SFValue:
        """Return the `SFValue` for **sf_id** by reading leaf 2/105 with idx1."""
        parsed = await self.dop2_get_parsed(device_id, 2, 105, idx1=sf_id, idx2=0)
        if not isinstance(parsed, SFValue):
            raise ValueError("Leaf did not return SFValue structure")
        return parsed

    async def set_setting(self, device_id: str, sf_id: int, new_value: int) -> None:
        """Write **new_value** to setting *sf_id* using leaf 2/105.

        This is *experimental* and assumes simple payload structure:
            <sf_id:u16> <new_value:u16>
        padded to blocksize 16.
        """
        sf = await self.get_setting(device_id, sf_id)

        if not (sf.minimum <= new_value <= sf.maximum):
            raise ValueError(f"Value {new_value} outside allowed range {sf.range}")

        payload = bytes([
            (sf_id >> 8) & 0xFF,
            sf_id & 0xFF,
            (new_value >> 8) & 0xFF,
            new_value & 0xFF,
        ])

        # DOP2 requires 16-byte block padding/ encryption handled by _put_request
        await self.dop2_write_leaf(device_id, 2, 105, payload, idx1=sf_id, idx2=0)

    # ---------------------------------------------------------------------
    # Phase 11 – Summary helper

    async def get_summary(self, device_id: str) -> DeviceSummary:
        """Return a consolidated overview for *device_id*."""
        ident_task = asyncio.create_task(self.get_device_ident(device_id))
        state_task = asyncio.create_task(self.get_device_state(device_id))

        combined_state_task = asyncio.create_task(
            self.dop2_get_parsed(device_id, 2, 256)
        )

        ready_task = asyncio.create_task(self.can_remote_start(device_id))

        ident = await ident_task
        state = await state_task

        combined = None
        try:
            parsed = await combined_state_task
            from asyncmiele.dop2.models import DeviceCombinedState

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

    async def get_consumption_stats(self, device_id: str) -> ConsumptionStats:
        """Return cumulative consumption counters for *device_id*.

        This helper fetches leaves 2/119 (hours-of-operation) and 2/138 (cycle counter).
        If a leaf is missing or cannot be parsed the corresponding field is ``None``.
        """
        hrs_task = asyncio.create_task(self.dop2_get_parsed(device_id, 2, 119))
        cyc_task = asyncio.create_task(self.dop2_get_parsed(device_id, 2, 138))
        totals_task = asyncio.create_task(self.dop2_get_parsed(device_id, 2, 6195))

        hours: int | None = None
        cycles: int | None = None
        energy_wh: int | None = None
        water_l: int | None = None

        try:
            res = await hrs_task
            if isinstance(res, int):
                hours = res
        except Exception:
            pass

        try:
            res = await cyc_task
            if isinstance(res, int):
                cycles = res
        except Exception:
            pass

        try:
            res = await totals_task
            if isinstance(res, dict):
                energy_wh = res.get("energy_wh_total")
                water_l = res.get("water_l_total")
        except Exception:
            pass

        return ConsumptionStats(
            hours_of_operation=hours,
            cycles_completed=cycles,
            energy_wh_total=energy_wh,
            water_l_total=water_l,
        ) 