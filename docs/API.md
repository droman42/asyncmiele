# AsyncMiele API Documentation

This document describes the AsyncMiele API for communicating with Miele@Home devices.

## MieleClient

The main client class for interacting with Miele devices.

### Initialization

```python
from asyncmiele import MieleClient

client = MieleClient(
    host="192.168.1.123",
    group_id=bytes.fromhex("your_group_id"),
    group_key=bytes.fromhex("your_group_key"),
    timeout=5.0  # Optional, defaults to 5.0 seconds
)
```

Parameters:
- `host`: The IP address or hostname of the Miele device
- `group_id`: GroupID as bytes (use `bytes.fromhex()` to convert from a hex string)
- `group_key`: GroupKey as bytes (use `bytes.fromhex()` to convert from a hex string)
- `timeout`: Optional timeout for API requests in seconds (default: 5.0)

### Methods

#### `async get_devices() -> Dict[str, MieleDevice]`

Get all available devices.

Returns a dictionary mapping device IDs to `MieleDevice` objects.

```python
devices = await client.get_devices()
for device_id, device in devices.items():
    print(f"Device {device_id}: {device.name}")
```

#### `async get_device(device_id: str) -> MieleDevice`

Get a specific device by ID.

Parameters:
- `device_id`: The ID of the device to retrieve

Returns a `MieleDevice` object.

```python
device = await client.get_device("your_device_id")
print(f"Device name: {device.name}")
print(f"Device status: {device.state.status}")
```

#### `async get_device_state(device_id: str) -> DeviceState`

Get the current state of a specific device.

Parameters:
- `device_id`: The ID of the device to retrieve state for

Returns a `DeviceState` object.

```python
state = await client.get_device_state("your_device_id")
print(f"Status: {state.status}")
print(f"Program: {state.program_type}")
```

#### `async get_device_ident(device_id: str) -> DeviceIdentification`

Get the identification information for a specific device.

Parameters:
- `device_id`: The ID of the device to retrieve identification for

Returns a `DeviceIdentification` object.

```python
ident = await client.get_device_ident("your_device_id")
print(f"Device name: {ident.device_name}")
print(f"Device type: {ident.device_type}")
```

#### `async register() -> bool`

Register this client with the Miele device.

Returns `True` if registration was successful.

```python
success = await client.register()
if success:
    print("Registration successful")
```

#### `async easy_setup(host: str) -> Tuple[str, str, str]`

Class method to create a new client and register it with a device.

Parameters:
- `host`: The IP address or hostname of the Miele device

Returns a tuple of `(device_id, group_id, group_key)`.

```python
device_id, group_id, group_key = await MieleClient.easy_setup("192.168.1.123")
print(f"Device ID: {device_id}")
print(f"GroupID: {group_id}")
print(f"GroupKey: {group_key}")
```

## Models

### MieleDevice

Represents a Miele device with its identification and state information.

Properties:
- `id`: The device ID
- `ident`: Device identification (`DeviceIdentification`)
- `state`: Device state (`DeviceState`)
- `name`: The device name or tech type if name is not available

### DeviceState

Represents the state of a Miele device.

Properties:
- `status`: Current status of the device
- `program_id`: Program ID
- `program_type`: Type of program currently running
- `program_phase`: Current phase of the program
- `remaining_time`: Remaining time in seconds
- `start_time`: Start time in seconds
- `elapsed_time`: Elapsed time in seconds
- `raw_state`: Raw state data from the API

### DeviceIdentification

Represents identification information for a Miele device.

Properties:
- `device_name`: Name of the device
- `device_type`: Type of the device
- `fab_number`: Fabrication number (serial number)
- `tech_type`: Technical type of the device

## Utility Functions

### `async discover_devices(timeout: float = 5.0) -> List[Dict[str, Any]]`

Discover Miele devices on the local network using UPnP/SSDP.

Parameters:
- `timeout`: Discovery timeout in seconds

Returns a list of discovered devices with their host address and other information.

```python
from asyncmiele import discover_devices

devices = await discover_devices()
for device in devices:
    print(f"Found device at {device['host']}")
```

### `async get_device_info(host: str, timeout: float = 5.0) -> Dict[str, Any]`

Get basic device information without authentication.

Parameters:
- `host`: Device IP address or hostname
- `timeout`: Request timeout in seconds

Returns a dictionary of device information.

```python
from asyncmiele import get_device_info

info = await get_device_info("192.168.1.123")
print(f"Device info: {info}")
```

### `async easy_setup(host: str) -> Tuple[str, str, str]`

Set up a new client with a Miele device.

Parameters:
- `host`: IP address or hostname of the Miele device

Returns a tuple of `(device_id, group_id, group_key)` for storing in configuration.

```python
from asyncmiele import easy_setup

device_id, group_id, group_key = await easy_setup("192.168.1.123")
```

## Exceptions

AsyncMiele provides a hierarchy of exceptions for proper error handling:

- `MieleException`: Base exception for all AsyncMiele exceptions
  - `APIException`: Base for API-related errors
    - `DeviceNotFoundError`: Device not found
    - `InvalidPathError`: Invalid API path
    - `DecryptionError`: Response decryption failed
    - `ParseError`: Response parsing failed
  - `NetworkException`: Base for network-related errors
    - `ConnectionError`: Connection failed
    - `TimeoutError`: Request timed out
    - `ResponseError`: Server returned error status
  - `AuthenticationException`: Base for authentication errors
    - `InvalidCredentialsError`: Invalid GroupID or GroupKey
    - `AuthorizationError`: Not authorized to access resource
    - `RegistrationError`: Device registration failed 