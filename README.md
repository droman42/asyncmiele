# AsyncMiele

An asynchronous Python client for Miele@Home devices. It's a full rewrite of the [home-assistant-miele-mobile](https://github.com/thuxnder/home-assistant-miele-mobile) project with a focus of decoupling the API from Home Assistant.
This library also integrates some functionality from the [MieleRESTServer](https://github.com/akappner/MieleRESTServer) project for those who can't afford running an extra server.
It also integrates some convenience functions from the [pymiele](https://github.com/nordicopen/pymiele) project, but doesn't require to communicate thru Miele cloud.

This library provides a simple, asynchronous interface to communicate with Miele appliances that support the Miele@Home protocol over local network (e.g., via XKM3100W module or built-in WiFi).

## Why a new library?

The original [home-assistant-miele-mobile](https://github.com/thuxnder/home-assistant-miele-mobile) project is a great project, but it's tightly coupled to Home Assistant. Those, who don't use Home Assistant, can't use this project.
The original [MieleRESTServer](https://github.com/akappner/MieleRESTServer) project is a great project, but it requires to run an extra REST server, which can be too much to run on a home automation controller.
The original [pymiele](https://github.com/nordicopen/pymiele) project is a great project, but it requires to communicate thru Miele cloud. It is a very strong limitation for countries, which aren't supported by Miele cloud and for users, who prefer their home automation to be fully isolated on the local network.

The library is a async merge of all 3 projects, mentioned above and is designed to integrate with any home automation system, which supports asyncio. 

## Features

- Asynchronous API using modern Python async/await syntax
- Connect to Miele devices over local network (no cloud dependency)
- Configuration-driven service architecture for production use
- Clean 3-step device setup process
- Enhanced capability detection and management
- Comprehensive device profile system with JSON storage
- Retrieve device information and status
- Proper error handling and type hints
- Clean, object-oriented design

## Installation

```bash
pip install asyncmiele
```

## Quick Start

### Configuration-Driven Service Integration (Recommended)

For production services, use the configuration-driven approach with JSON profiles:

```python
import asyncio
from asyncmiele import Appliance

async def service_integration():
    # Load device from configuration file (includes credentials, capabilities, etc.)
    appliance = await Appliance.from_config_file("kitchen_oven_config.json")
    
    # Device is ready to use with full capability checking
    if appliance.has_all_capabilities("WAKE_UP", "REMOTE_START"):
        await appliance.wake_up()
        await appliance.remote_start(allow_remote_start=True)
    
    # Get current status
    summary = await appliance.summary()
    print(f"Progress: {summary.progress}")

asyncio.run(service_integration())
```

### Manual Client Setup (Development/Testing)

For development or when you need manual control:

```python
import asyncio
from asyncmiele import MieleClient, Appliance

async def manual_setup():
    # Create client with stored credentials
    client = MieleClient.from_hex(
        host="192.168.1.100",
        group_id_hex="your_group_id",
        group_key_hex="your_group_key"
    )
    
    async with client:
        # Create appliance instance
        appliance = Appliance(client, "000123456789")
        
        # Use appliance
        summary = await appliance.summary()
        print(f"Progress: {summary.progress}")

asyncio.run(manual_setup())
```

## Device Setup Process

The library provides a streamlined 3-step configuration workflow for setting up new devices:

### Step 1: Discover Devices in Setup Mode

Find devices that are ready for configuration:

```bash
python scripts/discover_setup_devices.py
```

Output shows devices with their information:
```
✅ Device found at 192.168.1.100
📋 Device ID: 000160829578          ← Save this ID for Step 3
🏷️  Device Type: Oven
🔧 Setup Mode: True
🔑 Temporary SSID: Miele_ABC123     ← Use this SSID for Step 2
```

### Step 2: Configure Device WiFi

**Important:** Before running this script, manually connect your computer to the device's WiFi access point (e.g., "Miele_ABC123" from Step 1).

Configure the device to connect to your home WiFi network:

```bash
python scripts/configure_device_wifi.py \
    --ssid "YourHomeWiFi" \
    --password "your_wifi_password"
```

This script sends the WiFi configuration directly to the device using the same approach as MieleRESTServer. The device will disconnect from its access point and connect to your WiFi network, receiving a new IP address.

**Note:** The script assumes you are already connected to the device's temporary WiFi access point. This manual connection step ensures reliable communication during WiFi configuration.

**Testing:** Use `--dry-run` to see what configuration would be sent without actually sending it:
```bash
python scripts/configure_device_wifi.py --ssid "YourHomeWiFi" --password "your_wifi_password" --dry-run
```

### Step 3: Create Device Profile

Generate the complete device configuration using the device ID from Step 1:

```bash
python scripts/create_device_profile.py \
    --host 192.168.1.100 \
    --device-id 000160829578 \
    --device-name "Kitchen Oven" \
    --output kitchen_oven_config.json
```

This script will:
- Generate and provision security credentials
- Detect device capabilities
- Extract the program catalog
- Create a complete JSON configuration file

### Configuration File Format

The generated configuration file contains everything needed for service integration:

```json
{
  "device_id": "000160829578",
  "device_type": "Oven",
  "friendly_name": "Kitchen Oven",
  "host": "192.168.1.100",
  "timeout": 5.0,
  "credentials": {
    "group_id": "29dab98f50adf5b0",
    "group_key": "244232e1c0abd062bf2a5f457834063f23baa8e44b1b7cfeba44c26560bc7ee901cc99d56e865729bbfbcd08fce4dba740cf6ca78dc9faba089b7d956b8bfcfc"
  },
  "capabilities": {
    "supported": ["WAKE_UP", "REMOTE_START", "PROGRAM_CATALOG"],
    "failed": ["LIGHT_CONTROL"],
    "detection_date": "2024-01-15T10:30:00Z"
  },
  "program_catalog": {
    "device_type": "Oven",
    "extraction_method": "dop2_new",
    "programs": {
      "baking": {
        "id": 1,
        "name": "Baking",
        "options": [
          {"id": 101, "name": "Temperature", "min": 30, "max": 250}
        ]
      }
    }
  }
}
```

### Using Configuration Files in Services

Once you have a configuration file, using the device in your service is simple:

```python
import asyncio
from asyncmiele import Appliance

async def my_service():
    # Load complete device configuration
    appliance = await Appliance.from_config_file("kitchen_oven_config.json")
    
    # All capabilities are automatically available
    if appliance.has_capability("REMOTE_START"):
        await appliance.remote_start(allow_remote_start=True)
    
    # Program catalog is automatically loaded
    programs = await appliance.get_available_programs()
    print(f"Available programs: {list(programs.keys())}")

asyncio.run(my_service())
```

## Device Capabilities

The library provides an enhanced capability system using set-based operations for efficient capability checking:

### Capability Checking with Configuration

When using configuration files, capability information is automatically loaded:

```python
import asyncio
from asyncmiele import Appliance, DeviceCapability

async def capability_example():
    appliance = await Appliance.from_config_file("device_config.json")
    
    # Check single capability
    if appliance.has_capability(DeviceCapability.WAKE_UP):
        await appliance.wake_up()
    
    # Check multiple capabilities (all required)
    required_caps = [DeviceCapability.WAKE_UP, DeviceCapability.REMOTE_START]
    if appliance.has_all_capabilities(*required_caps):
        await appliance.wake_up()
        await appliance.remote_start(allow_remote_start=True)
    
    # Check multiple capabilities (any will do)
    control_caps = [DeviceCapability.REMOTE_START, DeviceCapability.PROGRAM_CONTROL]
    if appliance.has_any_capability(*control_caps):
        print("Device supports some form of remote control")
    
    # Get all supported capabilities
    capabilities = appliance.get_supported_capabilities()
    print(f"Supported: {[cap.name for cap in capabilities]}")

asyncio.run(capability_example())
```

### Manual Capability Detection

For manual setup or testing, you can detect capabilities directly:

```python
from asyncmiele import MieleClient
from asyncmiele.capabilities import detect_capabilities_as_sets

async def detect_capabilities():
    client = MieleClient.from_hex(host, group_id, group_key)
    
    async with client:
        # Detect capabilities and get as sets
        supported, failed = await detect_capabilities_as_sets(client, device_id)
        
        print(f"Supported: {[cap.name for cap in supported]}")
        print(f"Failed: {[cap.name for cap in failed]}")

asyncio.run(detect_capabilities())
```

## Connection Management

The library includes built-in connection management and health monitoring when using the configuration-driven approach:

```python
import asyncio
from asyncmiele import Appliance

async def connection_management_example():
    # Configuration files include connection parameters and timeout settings
    appliance = await Appliance.from_config_file("device_config.json")
    
    # Built-in connection management handles:
    # - Automatic retries
    # - Connection pooling
    # - Health monitoring
    # - Network failure recovery
    
    # Use appliance normally - connection management is automatic
    summary = await appliance.summary()
    print(f"Device status: {summary.status}")

asyncio.run(connection_management_example())
```

## DOP2 Tree Visualization

The library includes tools for exploring and visualizing the DOP2 tree structure of Miele devices:

```python
async def dop2_exploration():
    appliance = await Appliance.from_config_file("device_config.json")
    
    # Generate HTML visualization
    await appliance.visualize_dop2_tree(
        output_file="dop2_tree.html",
        format_type="html",
        known_only=True  # Only explore known attributes
    )
    
    # Generate ASCII visualization for console
    await appliance.visualize_dop2_tree(
        output_file="dop2_tree.txt",
        format_type="ascii"
    )

asyncio.run(dop2_exploration())
```

You can also use the standalone script:

```bash
# Explore device DOP2 tree
python scripts/visualize_dop2_tree.py --config device_config.json --output-dir ./output
```

## Migration from Manual Setup

If you have existing code using manual client setup, migration to the configuration-driven approach is straightforward:

### Before (Manual Setup):
```python
# Old manual approach
client = MieleClient.from_hex(host, group_id, group_key)
appliance = Appliance(client, device_id)

# Manual capability checking
if await client.has_capability(device_id, DeviceCapability.REMOTE_START):
    await client.remote_start(device_id, allow_remote_start=True)
```

### After (Configuration-Driven):
```python
# New configuration-driven approach
appliance = await Appliance.from_config_file("device_config.json")

# Automatic capability checking
if appliance.has_capability(DeviceCapability.REMOTE_START):
    await appliance.remote_start(allow_remote_start=True)
```

### Creating Configuration from Existing Credentials

If you have existing credentials, create a configuration file:

```python
from asyncmiele.models.device_profile import DeviceProfile
from asyncmiele.models.credentials import MieleCredentials
from asyncmiele.config.loader import save_device_profile

# Create profile from existing credentials
profile = DeviceProfile(
    device_id="000123456789",
    host="192.168.1.100",
    timeout=5.0,
    credentials=MieleCredentials(
        group_id="your_group_id_hex",
        group_key="your_group_key_hex"
    )
)

# Save as configuration file
save_device_profile(profile, "device_config.json")

# Now use with configuration-driven approach
appliance = await Appliance.from_config_file("device_config.json")
```

## Troubleshooting

### Configuration Issues
- **Invalid JSON**: Use a JSON validator to check your configuration file format
- **Missing credentials**: Ensure the configuration file includes valid `group_id` and `group_key`
- **Network connectivity**: Verify the device's IP address in the `host` field is correct and reachable

### Device Setup Issues
- **Device not found in Step 1**: Make sure the device is in setup mode (usually by holding a button)
- **WiFi configuration fails in Step 2**: 
  - Ensure you are manually connected to the device's WiFi access point before running the script
  - Verify the WiFi credentials and security type are correct
  - Check that the device is reachable at 192.168.1.1 (or use --device-ip for different addresses)
- **Profile creation fails in Step 3**: Check network connectivity and device accessibility

### Runtime Issues
- **Device not responding**: The device may be in sleep mode - capability checking will automatically wake it
- **Remote start fails**: Verify the device has `REMOTE_START` capability and `allow_remote_start=True` is set
- **Program start fails**: Ensure the device has `PROGRAM_CONTROL` capability and a valid program catalog

For comprehensive troubleshooting, use the diagnostic script:

```bash
python scripts/device_diagnosis.py --config device_config.json
```

## Acknowledgments

This project is based on reverse-engineering efforts of the Miele@Home protocol and inspired by the [home-assistant-miele-mobile](https://github.com/thuxnder/home-assistant-miele-mobile) project. It has been refactored to be independent of Home Assistant and provide a clean, asynchronous API with configuration-driven service architecture.

## License

MIT

## Error Handling

The library provides detailed exception classes for proper error handling:

```python
import asyncio
from asyncmiele import Appliance
from asyncmiele.exceptions.network import NetworkConnectionError, NetworkTimeoutError
from asyncmiele.exceptions.api import DeviceNotFoundError
from asyncmiele.exceptions.config import InvalidConfigurationError

async def handle_errors():
    try:
        # Configuration-driven approach handles most connection issues automatically
        appliance = await Appliance.from_config_file("device_config.json")
        await appliance.wake_up()
        
    except InvalidConfigurationError as e:
        print(f"Configuration error: {e}")
    except NetworkConnectionError as e:
        print(f"Connection failed: {e}")
    except NetworkTimeoutError as e:
        print(f"Request timed out: {e}")
    except DeviceNotFoundError as e:
        print(f"Device not found: {e}")

asyncio.run(handle_errors())
```

### Waking Up a Device

If a Miele appliance has gone into power-saving "sleep" mode it returns invalid data.  
Use the `wake_up()` helper to bring it online again:

```python
# Configuration-driven approach
appliance = await Appliance.from_config_file("device_config.json")
await appliance.wake_up()

# Or with manual client
await client.wake_up("000123456789")  # device route / ID
```

This sends `{"DeviceAction": 2}` to the device and usually completes with an empty 204-No-Content response.

### Remote-Start (opt-in)

Starting a program remotely can be dangerous if the appliance is not prepared correctly.  
For this reason **remote-start is disabled by default**.  Enable it in one of two ways:

```python
from asyncmiele.config import settings
settings.enable_remote_start = True        # global once-per-process
```

or pass an explicit override flag per call:

```python
await appliance.remote_start(allow_remote_start=True)
```

Before attempting a start you can check whether the appliance is ready:

```python
if await appliance.can_remote_start():
    await appliance.remote_start(allow_remote_start=True)
else:
    print("Device not ready for remote start")
```

Remote-start issues `{"ProcessAction": 1}` to the `/State` resource.  The device must already have a fully programmed cycle and expose the `RemoteEnable` flag (`15`).

## Enhanced Appliance Class Features

The library provides an enhanced `Appliance` class that offers comprehensive device management:

### Property Accessors

Convenient property accessors for common state information:

```python
async def monitor_appliance():
    appliance = await Appliance.from_config_file("device_config.json")
    
    # Check if a program is running
    if await appliance.is_running:
        # Get the current program phase
        phase = await appliance.program_phase
        print(f"Current phase: {phase}")
        
        # Get the remaining time in minutes
        remaining = await appliance.remaining_time
        print(f"Remaining time: {remaining} minutes")
        
        # Get temperature information
        current_temp = await appliance.current_temperature
        target_temp = await appliance.target_temperature
        print(f"Temperature: {current_temp}°C / Target: {target_temp}°C")

asyncio.run(monitor_appliance())
```

### State Change Notifications

Monitor state changes with callbacks:

```python
async def on_state_change(state):
    print(f"State changed: {state}")
    
async def on_program_finished():
    print("Program finished!")
    # Send notification or trigger other actions

async def monitor_with_callbacks():
    appliance = await Appliance.from_config_file("device_config.json")
    
    # Register callbacks
    await appliance.register_state_callback(on_state_change)
    await appliance.register_program_finished_callback(on_program_finished)
    
    # Later, unregister when no longer needed
    await appliance.unregister_state_callback(on_state_change)

asyncio.run(monitor_with_callbacks())
```

### Program Control with Configuration

With configuration files, program catalogs are automatically loaded:

```python
async def program_control():
    appliance = await Appliance.from_config_file("device_config.json")
    
    # Get available programs (loaded from configuration)
    programs = await appliance.get_available_programs()
    print(f"Available programs: {list(programs.keys())}")
    
    # Start a program with options
    if appliance.has_capability("PROGRAM_CONTROL"):
        await appliance.start_with_options(
            "Normal", 
            temperature=60, 
            spin_speed=1200,
            extra_rinse=True
        )
        print("Program started")

asyncio.run(program_control())
```

## Configuration Validation

The library includes comprehensive configuration validation:

```python
from asyncmiele.validation.config import ConfigurationValidator

async def validate_config():
    validator = ConfigurationValidator()
    
    # Load and validate a configuration file
    profile = load_device_profile("device_config.json")
    result = await validator.validate_profile(profile)
    
    if result.success:
        print("✅ Configuration is valid")
    else:
        print("❌ Configuration issues found:")
        for issue in result.issues:
            print(f"  - {issue}")

asyncio.run(validate_config())
```

## Utility Scripts

### Configuration Management Scripts

The library includes streamlined scripts for device setup:

**Discovery and Setup:**
```bash
# Step 1: Find devices in setup mode
python scripts/discover_setup_devices.py

# Step 2: Configure WiFi (manual connection to device required)
python scripts/configure_device_wifi.py --ssid "YourWiFi" --password "password"

# Step 3: Create complete profile
python scripts/create_device_profile.py --host 192.168.1.100 --device-id 000123456789 --output config.json
```

**Diagnostic and Maintenance:**
```bash
# Device diagnosis and troubleshooting
python scripts/device_diagnosis.py --config device_config.json

# Factory reset (if needed)
python scripts/device_factory_reset.py --config device_config.json

# DOP2 tree exploration (development)
python scripts/dop2_explorer.py --config device_config.json
python scripts/visualize_dop2_tree.py --config device_config.json
```
