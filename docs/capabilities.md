# Device Capability Detection

This document explains how to use the device capability detection system in the asyncmiele library to detect and adapt to the capabilities of different Miele devices.

## Overview

Miele devices have varying capabilities depending on their type, firmware version, and configuration. The capability detection system in asyncmiele allows you to:

1. Automatically detect what capabilities a device supports
2. Adapt your code's behavior based on available capabilities
3. Handle unsupported operations gracefully
4. Track capability testing results for future reference

## Device Capabilities

The following capabilities are defined in the `DeviceCapability` enum:

| Capability | Description |
|------------|-------------|
| STATE_REPORTING | Device can report its state |
| PROGRAM_REPORTING | Device can report current program |
| WAKE_UP | Device supports wake-up commands |
| REMOTE_START | Device supports remote start control |
| REMOTE_CONTROL | Device supports remote control |
| PROGRAM_CATALOG | Device has a program catalog |
| PROGRAM_SELECTION | Device supports program selection |
| PARAMETER_SELECTION | Device supports parameter selection |
| DOP2_BASIC | Device supports basic DOP2 access |
| DOP2_ADVANCED | Device supports advanced DOP2 features |
| CONSUMPTION_STATS | Device provides consumption statistics |

## Using the Capability Detection System

### Detecting Device Capabilities

The `MieleClient` class now includes a `detect_capabilities` method that performs tests to determine what capabilities a device supports:

```python
from asyncmiele import MieleClient, DeviceCapability

async with MieleClient(...) as client:
    # Detect capabilities
    capabilities = await client.detect_capabilities(device_id)
    
    # Check if a specific capability is supported
    if DeviceCapability.PROGRAM_CATALOG in capabilities:
        print("Device supports program catalog")
```

### Using Device Profiles

For a more integrated approach, you can use the `DeviceProfile` class to store device configuration, credentials, and capabilities:

```python
from asyncmiele import MieleClient, DeviceProfile, MieleCredentials, MieleDeviceConfig

# Create configuration and credentials
config = MieleDeviceConfig(host="192.168.1.100")
credentials = MieleCredentials(group_id="...", group_key="...")

# Create device profile
profile = DeviceProfile(
    device_id="000123456789",
    config=config,
    credentials=credentials
)

# Create client from profile
client = MieleClient.from_profile(profile)

async with client:
    # Detect capabilities (updates the profile automatically)
    await client.detect_capabilities(profile.device_id)
    
    # Check capability in the profile
    if profile.has_capability(DeviceCapability.REMOTE_START):
        await client.remote_start(profile.device_id, allow_remote_start=True)
```

## Using the Appliance Class with Capabilities

The high-level `Appliance` class now integrates with the capability detection system, providing a more user-friendly interface:

```python
from asyncmiele import MieleClient, Appliance, DeviceCapability, DeviceProfile

# Create client
client = MieleClient(...)

# Create appliance with device profile
profile = DeviceProfile(...)
appliance = await Appliance.from_profile(client, profile)

# Or create appliance directly
appliance = Appliance(client, device_id="000123456789")

# Check capabilities
if await appliance.has_capability(DeviceCapability.PROGRAM_CATALOG):
    # Get available programs
    programs = await appliance.get_available_programs()
    print(f"Found {len(programs)} programs")

# Methods will automatically check capabilities
try:
    await appliance.start_program("Cotton")
except ProgramError as e:
    print(f"Cannot start program: {e}")
```

Benefits of using the Appliance class with capabilities:

1. **Automatic capability checking**: Methods like `start_program` will check if the required capabilities are available before attempting operations
2. **Improved error handling**: More specific error messages when a capability is not supported
3. **Adaptive behavior**: Methods can adapt their behavior based on available capabilities (e.g., waking up the device before operations if supported)
4. **Integrated with device profiles**: You can create an Appliance directly from a DeviceProfile with `Appliance.from_profile()`

### Handling Unsupported Capabilities

When a method requires a capability that a device doesn't support, it will raise an `UnsupportedCapabilityError`:

```python
from asyncmiele.exceptions.config import UnsupportedCapabilityError

async with client:
    try:
        await client.extract_program_catalog(device_id)
    except UnsupportedCapabilityError as e:
        print(f"Cannot extract program catalog: {e}")
        # Handle the situation gracefully
```

## Testing and Diagnostics

You can use the included `test_capabilities.py` script to test what capabilities a device supports:

```bash
python scripts/test_capabilities.py --host 192.168.1.100 --device-id 000123456789 --group-id ... --group-key ...
```

This will run a series of tests to determine what capabilities the device supports and generate a detailed report.

## Capability-Aware API Methods

The following API methods are now capability-aware:

- `wake_up` - Requires the WAKE_UP capability
- `can_remote_start` - Requires the REMOTE_START capability
- `remote_start` - Requires the REMOTE_START capability
- `extract_program_catalog` - Requires the PROGRAM_CATALOG capability

These methods will automatically record whether the device supports the capability when called, and will raise an `UnsupportedCapabilityError` if the capability is known to be unsupported.

## Default Capabilities by Device Type

The library includes default capability profiles for different device types, which serve as a starting point for capability detection:

- Washing machines: STATE_REPORTING, PROGRAM_REPORTING, WAKE_UP, REMOTE_START, PROGRAM_CATALOG, DOP2_BASIC
- Tumble dryers: STATE_REPORTING, PROGRAM_REPORTING, WAKE_UP, REMOTE_START, PROGRAM_CATALOG, DOP2_BASIC
- Dishwashers: STATE_REPORTING, PROGRAM_REPORTING, WAKE_UP, REMOTE_START, PROGRAM_CATALOG, DOP2_BASIC
- Ovens: STATE_REPORTING, PROGRAM_REPORTING, WAKE_UP, REMOTE_START, PROGRAM_CATALOG, DOP2_BASIC

These defaults are used as a starting point for capability detection, but the actual capabilities are determined by testing the device. 