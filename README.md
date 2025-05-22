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
- Retrieve device information and status
- Proper error handling and type hints
- Clean, object-oriented design

## Installation

```bash
pip install asyncmiele
```

## Usage

### Device Setup

Before using the library, you need to register it with your Miele device. The device must be in registration mode (typically after being connected to WiFi but not yet configured with the Miele mobile app).

```python
import asyncio
from asyncmiele import easy_setup

async def register_device():
    # IP address of your Miele device
    device_ip = "192.168.1.123"
    
    # Register with the device
    device_id, group_id, group_key = await easy_setup(device_ip)
    
    print(f"Successfully registered with device {device_id}")
    print(f"GroupID: {group_id}")
    print(f"GroupKey: {group_key}")
    # Store these credentials securely for future use

asyncio.run(register_device())
```

### Re-initializing a Device Already on the Network

If your Miele device is already connected to your network (either through the Miele@mobile app or previous setup), follow these steps to re-initialize it for use with asyncmiele:

#### 1. Reset the device to registration mode

You have two options:

**Option A: Keep your existing Miele@mobile app connection**
- Use network sniffing tools to capture the GroupID and GroupKey used by the Miele@mobile app
- Look for HTTP PUT requests to `/Security/Commissioning/` during device setup
- Extract the GroupID and GroupKey from the request body

**Option B: Remove device from the Miele@mobile app**
- Open the Miele@mobile app
- Go to Settings > Device Management
- Select your device and remove it from the app
- This will keep the device on your WiFi but put it back in registration mode

#### 2. Discover the device on your network

Use the discovery example to find your device:

```bash
# From the asyncmiele directory
python examples/discover_network.py
```

This will show all Miele devices in registration mode on your network, including their IP addresses.

#### 3. Register with the device

Use the setup script to register with your device:

```bash
python examples/setup.py --host 192.168.1.123
```

#### 4. Store the credentials securely

The registration process will return three critical pieces of information:
- `device_id`: The unique identifier for your device
- `group_id`: The GroupID used for authentication (hexadecimal string)
- `group_key`: The GroupKey used for encryption (hexadecimal string)

Store these values securely. They are required for all future connections to the device.

For example, save them in a configuration file:

```python
# config.py
MIELE_CONFIG = {
    "host": "192.168.1.123",
    "device_id": "1234567890",
    "group_id": "0123456789abcdef",
    "group_key": "0123456789abcdef..." # Long hex string
}
```

#### 5. Connect to the device using stored credentials

```python
import asyncio
from asyncmiele import MieleClient
from config import MIELE_CONFIG

async def connect_to_device():
    client = MieleClient(
        host=MIELE_CONFIG["host"],
        group_id=bytes.fromhex(MIELE_CONFIG["group_id"]),
        group_key=bytes.fromhex(MIELE_CONFIG["group_key"])
    )
    
    # Now you can use the client to interact with your device
    device = await client.get_device(MIELE_CONFIG["device_id"])
    print(f"Connected to {device.name}")

asyncio.run(connect_to_device())
```

### Quick-start (new convenience layer)

```python
import asyncio
from asyncmiele import MieleClient

# Credentials obtained during registration
HOST = "192.168.1.123"
GROUP_ID = "0123456789abcdef"
GROUP_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
DEVICE_ID = "000123456789"


async def main():
    # from_hex converts the stored hex strings → bytes
    client = MieleClient.from_hex(HOST, GROUP_ID, GROUP_KEY)

    async with client:  # persistent HTTP session
        # High-level proxy bound to a single appliance
        washer = await client.device(DEVICE_ID)

        summary = await washer.summary()
        print("Progress", summary.progress)

        # Wake up the appliance and start pre-programmed cycle
        await washer.wake_up()
        if await washer.can_remote_start():
            await washer.remote_start(allow_remote_start=True)


asyncio.run(main())
```

The traditional low-level API (`get_devices`, `wake_up`, `remote_start`, …) is
still available, but the convenience layer requires far less boilerplate.

### Enhanced Appliance Class

The library provides an enhanced `Appliance` class that offers a comprehensive interface for managing Miele devices throughout their lifecycle.

#### Basic Usage

```python
import asyncio
from asyncmiele import MieleClient
from asyncmiele.appliance import Appliance

async def basic_usage():
    client = MieleClient.from_hex(HOST, GROUP_ID, GROUP_KEY)
    
    async with client:
        # Create an appliance instance
        async with Appliance(client, DEVICE_ID) as appliance:
            # Check if device is connected
            if not await appliance.is_connected():
                print("Device not connected")
                return
                
            # Get current state
            state = await appliance.get_state()
            print(f"Current state: {state}")
            
            # Start a program with user-friendly options
            if await appliance.is_ready:
                await appliance.start_with_options(
                    "Normal", 
                    temperature=60, 
                    spin_speed=1200,
                    extra_rinse=True
                )
                print("Program started")

asyncio.run(basic_usage())
```

#### Custom Program Catalogs

The Appliance class can be initialized with a custom program catalog:

```python
# Define a custom program catalog
custom_catalog = {
    "device_type": "washing_machine",
    "programs": [
        {
            "id": 1,
            "name": "Quick Wash",
            "options": [
                {
                    "id": 10,
                    "name": "Temperature",
                    "default": 30,
                    "allowed_values": [20, 30, 40, 60]
                },
                {
                    "id": 11,
                    "name": "Spin Speed",
                    "default": 800,
                    "allowed_values": [400, 800, 1200, 1400]
                }
            ]
        }
    ]
}

# Create an appliance with the custom catalog
appliance = Appliance(client, DEVICE_ID, custom_catalog=custom_catalog)

# Or load from configuration
config = {
    "device_id": DEVICE_ID,
    "program_catalog": custom_catalog
}
appliance = await Appliance.from_config(client, DEVICE_ID, config)

# Later update the catalog via configure method
await appliance.configure({"program_catalog": updated_catalog})
```

This allows third-party applications to provide their own program definitions without having to extract them from devices first.

#### Property Accessors

The Appliance class provides convenient property accessors for common state information:

```python
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
```

#### State Change Notifications

Monitor state changes with callbacks:

```python
async def on_state_change(state):
    print(f"State changed: {state}")
    
async def on_program_finished():
    print("Program finished!")
    # Send notification or trigger other actions

# Register callbacks
await appliance.register_state_callback(on_state_change)
await appliance.register_program_finished_callback(on_program_finished)

# Later, unregister when no longer needed
await appliance.unregister_state_callback(on_state_change)
```

#### Batch Operations

Perform multiple operations efficiently:

```python
# Set multiple settings at once
await appliance.batch_set_settings(
    temperature_unit="celsius",
    display_brightness=80,
    sound_volume=2
)

# Get multiple state properties in a single call
states = await appliance.get_multiple_states([
    "status", "programPhase", "remainingTime", "temperature"
])
```

#### Wait for Conditions

Wait for specific conditions:

```python
# Wait for program to finish (with 1 hour timeout)
finished = await appliance.wait_for(
    lambda state: state.get("programPhase") == "Finished",
    timeout=3600
)

# Wait until the appliance is ready for commands
ready = await appliance.wait_until_ready(timeout=30)
```

#### Configuration Management

Save and load configurations:

```python
# Save current configuration
await appliance.save_config("washer_config.json")

# Create from saved configuration
config = json.load(open("washer_config.json"))
new_appliance = await Appliance.from_config(client, DEVICE_ID, config)

# Configure with specific settings
await appliance.configure({
    "settings": {
        "temperature_unit": "celsius",
        "display_brightness": 80
    },
    "monitoring": {
        "interval": 10.0
    },
    "cache": {
        "default_ttl": 20.0
    }
})
```

#### Simulation Mode for Testing

Test your code without actual devices:

```python
from asyncmiele.appliance import SimulationMode

# Create an appliance in simulation mode
appliance = Appliance(client, DEVICE_ID, simulation_mode=SimulationMode.NORMAL)

# Later enable/disable simulation
await appliance.enable_simulation_mode(SimulationMode.FAILURE)  # Test error handling
await appliance.disable_simulation_mode()  # Back to real device
```

#### Async Iterator Support

Use the appliance as an async iterator to monitor state changes:

```python
async def monitor_state():
    async with Appliance(client, DEVICE_ID) as appliance:
        # Print state every monitoring interval
        async for state in appliance:
            print(f"Current state: {state}")
            
            # Exit loop when program finishes
            if state.get("programPhase") == "Finished":
                break
```

### Error Handling

The library provides detailed exception classes for proper error handling:

```python
import asyncio
from asyncmiele import MieleClient
from asyncmiele.exceptions.network import NetworkConnectionError, NetworkTimeoutError
from asyncmiele.exceptions.api import DeviceNotFoundError

async def handle_errors():
    try:
        client = MieleClient(
            host="192.168.1.123",
            group_id=bytes.fromhex("your_group_id"),
            group_key=bytes.fromhex("your_group_key")
        )
        
        device = await client.get_device("non_existent_id")
        
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
await client.remote_start("000123456789", allow_remote_start=True)
```

Before attempting a start you can check whether the appliance is ready:

```python
if await client.can_remote_start("000123456789"):
    await client.remote_start("000123456789", allow_remote_start=True)
else:
    print("Device not ready for remote start")
```

Remote-start issues `{"ProcessAction": 1}` to the `/State` resource.  The device must already have a fully programmed cycle and expose the `RemoteEnable` flag (`15`).

## Dumping a programme catalogue from a live appliance 🔧

Phase 14 adds a small helper script that can pull the static programme/option list
straight out of a LAN-paired appliance and write it into the JSON format used by
`asyncmiele.programs.ProgramCatalog`.

```
python scripts/dump_program_catalog.py \
       --host 192.168.6.126 \
       --device-id 000123456789 \
       --group-id aabbccddeeff00112233445566778899 \
       --group-key 0123456789abcdeffedcba9876543210
```

Arguments

* `--host`      IP address (or mDNS name) of the appliance on your LAN.
* `--device-id` 12-digit identifier printed on the pairing sticker (same one you
  use with `client.remote_start()`).
* `--group-id`  32-character hex string for the **GroupID** obtained during
  pairing.
* `--group-key` 32-character hex string for the **GroupKey** (AES key).

Optional flags

* `--wake`  Send a *wake-up* PUT before reading (useful if the machine is in
  stand-by).
* `--out`   Custom output path; default is
  `resources/programs/<device_type>.json` where `<device_type>` is resolved
  automatically from the device's */Ident* information.

How it works

1. Queries `/Devices/<id>/Ident` to discover the device-type string.
2. Reads three DOP2 leaves:
   * `14/1570` – **PC_ListConfig**: list of programmes.
   * `14/1571` – **PC_ListItem**  : option list for each programme.
   * `14/2570` – string table used by the two leaves.
3. Decodes the binary structures, resolves human-readable strings and writes
   the resulting Python objects as pretty-printed JSON.

After running the command you will find something like
`resources/programs/washing_machine.json`; this file is picked up automatically
by `ProgramCatalog.for_device()` and by the *select
a programme* example in `examples/select_program.py`.

## Device Capabilities

The library provides a capability detection system that allows you to check if a device supports specific features before attempting to use them. This prevents errors when trying to use features that aren't available on a particular device model.

### Using Capabilities with the Appliance Class

The `Appliance` class automatically checks for capabilities before attempting operations:

```python
import asyncio
from asyncmiele import MieleClient, Appliance, DeviceCapability

async def capabilities_example():
    client = MieleClient.from_hex(HOST, GROUP_ID, GROUP_KEY)
    
    async with client:
        # Create appliance with device profile (contains capability information)
        device_id = "000123456789"
        device_profile = await client.get_device_profile(device_id)
        appliance = Appliance(client, device_id, device_profile=device_profile)
        
        # The appliance will automatically check capabilities before operations
        if await appliance.has_capability(DeviceCapability.REMOTE_CONTROL):
            await appliance.remote_start(allow_remote_start=True)
        else:
            print("Remote control not supported by this device")
            
        # Start program only works if program catalog capability is available
        try:
            await appliance.start_program("Normal")
        except UnsupportedCapabilityError as e:
            print(f"Cannot start program: {e}")
            
        # Get available capabilities
        capabilities = await appliance.get_capabilities()
        print("Device supports:", ", ".join(str(c) for c in capabilities))

asyncio.run(capabilities_example())
```

### Working with Capabilities Directly

You can also work with capabilities directly:

```python
from asyncmiele.capabilities import DeviceCapability, detector

async def check_capabilities():
    # Check if device profile supports capabilities
    supports_program_control = detector.has_capability(
        device_profile, 
        DeviceCapability.PROGRAM_CONTROL
    )
    
    # Get all supported capabilities for a device
    all_capabilities = detector.detect_capabilities(device_profile)
    
    # Check multiple capabilities at once
    required = [
        DeviceCapability.REMOTE_CONTROL,
        DeviceCapability.PROGRAM_CONTROL
    ]
    has_all = detector.has_all_capabilities(device_profile, required)
```

## Connection Management

The library includes connection management features for optimizing device connections, handling connection lifecycle, and recovering from network issues.

### Using ConnectionManager

The `ConnectionManager` provides pooled connections and automatic retries:

```python
import asyncio
from asyncmiele import ConnectionManager, DeviceProfile, MieleClient

async def connection_manager_example():
    # Create a connection manager with custom settings
    manager = ConnectionManager(
        max_connections=5,      # Maximum concurrent connections
        connection_timeout=10.0, # Connection timeout in seconds
        retry_count=3,          # Number of retry attempts
        retry_delay=2.0         # Delay between retries in seconds
    )
    
    # Start the manager
    async with manager:
        # Get a client for a specific device (reuses connections)
        device_id = "000123456789"
        profile = DeviceProfile(device_id, config, credentials)
        
        client = await manager.get_client(device_id, profile)
        
        # Use the client as normal
        device_state = await client.get_device_state(device_id)
        
        # Manager handles connection failures automatically
        try:
            await client.wake_up(device_id)
        except Exception as e:
            print(f"Operation failed even after retries: {e}")

asyncio.run(connection_manager_example())
```

### Connection Health Monitoring

The library provides health monitoring to detect and recover from connection issues:

```python
from asyncmiele import ConnectionHealthMonitor

async def health_monitoring_example():
    # Create connection manager
    manager = ConnectionManager()
    
    # Create health monitor
    monitor = ConnectionHealthMonitor(
        manager,
        check_interval=30.0,  # Check connections every 30 seconds
        max_failures=3        # Allow 3 failures before marking unhealthy
    )
    
    # Register health state change callback
    async def on_health_change(device_id, is_healthy):
        print(f"Device {device_id} health: {'healthy' if is_healthy else 'unhealthy'}")
        if not is_healthy:
            # Take recovery action
            await manager.reset_connection(device_id)
    
    # Start the monitor
    async with monitor:
        # Register callback
        monitor.register_health_callback(on_health_change)
        
        # Add device to monitor
        monitor.add_device(device_id, profile)
        
        # Run your application...
        await asyncio.sleep(300)  # Example: run for 5 minutes
```

### Device Reset Support

The library includes support for detecting factory resets and recovering devices:

```python
from asyncmiele import DeviceResetter

async def device_reset_example():
    # Create a device resetter
    resetter = DeviceResetter(
        discovery_timeout=10.0,
        recovery_timeout=120.0,
        max_retries=3
    )
    
    # Initialize with connection manager
    resetter.initialize(connection_manager)
    
    # Register for reset notifications
    async def on_device_reset(device_id):
        print(f"Device {device_id} has been reset to factory settings")
        # Attempt recovery
        recovered = await resetter.attempt_recovery(device_id)
        if recovered:
            print(f"Successfully recovered device {device_id}")
    
    resetter.register_reset_callback(on_device_reset)
    
    # Or manually initiate a reset
    await resetter.initiate_reset(client, device_id)
```

For more detailed information, see the [Connection Optimization documentation](docs/connection_optimization.md).

## Utility Scripts

### Getting Device Credentials

The library includes a utility script to easily obtain device credentials and save them to a JSON file:

```bash
# Discover devices on the network and select one:
python scripts/get_device_credentials.py --output credentials.json

# Connect directly to a device with known IP:
python scripts/get_device_credentials.py --host 192.168.1.123 --output credentials.json
```

This script will:
1. Either discover devices on your network or connect to the specified IP
2. Register with the device to obtain credentials
3. Save the credentials (device_id, group_id, group_key) to a JSON file
4. Display example usage code

The resulting JSON file can be used directly with the `Appliance` class:

```python
import json
from asyncmiele import MieleClient
from asyncmiele.appliance import Appliance

# Load credentials from file
with open("credentials.json", "r") as f:
    creds = json.load(f)
    
# Create client and appliance
client = MieleClient.from_hex(
    creds["host"],
    creds["group_id"],
    creds["group_key"]
)
appliance = Appliance(client, creds["device_id"])
```

### Dumping a programme catalogue from a live appliance 🔧



# Miele Device Setup Guide

This guide explains how to set up and provision Miele devices for local control using the asyncmiele library.

## Prerequisites

- Python 3.9 or higher
- asyncmiele library installed
- A Miele device that supports local control
- Network access to the device

## Setup Process Overview

Setting up a Miele device for local control involves three main steps:

1. **Connect to the device's access point** - When in setup mode, Miele devices create their own WiFi network.
2. **Configure the device's WiFi settings** - Tell the device which WiFi network it should connect to.
3. **Provision security credentials** - Generate and send security credentials to the device.

## Step 1: Generate Credentials

Before setting up the device, you can generate the security credentials that will be used:

```bash
python scripts/generate_credentials.py --format json --pretty --out credentials.json
```

This will create a file called `credentials.json` containing your GroupID and GroupKey.

## Step 2: Reset the Device (if necessary)

If your device is already connected to the Miele@home cloud, you'll need to reset it first:

1. Access the device's settings menu
2. Navigate to the Miele@home or network settings
3. Select "Reset" or "Deactivate"
4. Follow the on-screen instructions to reset the network configuration

Different Miele devices have different reset procedures, so refer to your device's manual for specific instructions.

## Step 3: Connect to the Device's Access Point

When a Miele device is in setup mode, it creates its own WiFi network with an SSID starting with "Miele@home".

You can scan for available Miele access points using:

```bash
python scripts/configure_device_wifi.py --scan
```

To connect to the access point automatically:

```bash
python scripts/configure_device_wifi.py --scan --auto-connect
```

If the connection fails, you may need to connect manually:

### Manual Connection to Access Point

The password for the access point depends on the SSID:
- If the SSID is just "Miele@home", the password is "secured-by-tls"
- If the SSID has a suffix like "Miele@home-TAA1234", the password is the device's serial number

Connect to the WiFi network using your operating system's network settings.

## Step 4: Configure the Device's WiFi Settings

Once connected to the device's access point, configure it to connect to your home WiFi:

```bash
python scripts/configure_device_wifi.py --ssid "YourHomeWiFi" --password "YourWiFiPassword" --security wpa2
```

Additional options:
- `--hidden` - If your WiFi network is hidden
- `--ap-host` - IP address of the device (default: 192.168.1.1)
- `--timeout` - Request timeout in seconds (default: 5.0)

The device will now connect to your WiFi network and will no longer be accessible via its access point.

## Step 5: Provision Security Credentials

After the device connects to your WiFi network, you need to determine its IP address. This can be done by:
- Checking your router's DHCP client list
- Using a network scanner
- Using the discover_devices.py script:

```bash
python scripts/discover_devices.py
```

Once you have the IP address, provision the security credentials:

```bash
python scripts/provision_device_keys.py --host 192.168.1.50 --credentials-file credentials.json
```

Or generate new credentials on the fly:

```bash
python scripts/provision_device_keys.py --host 192.168.1.50 --generate --output credentials.json
```

## Step 6: Test the Connection

After provisioning, you can test the connection using the MieleClient:

```python
from asyncmiele.api.client import MieleClient
import asyncio
import json

async def test_connection():
    # Load credentials
    with open('credentials.json', 'r') as f:
        creds = json.load(f)
    
    # Create client
    client = MieleClient.from_hex(
        host="192.168.1.50",
        group_id_hex=creds['group_id'],
        group_key_hex=creds['group_key']
    )
    
    # Test connection
    async with client:
        devices = await client.get_devices()
        print(f"Found {len(devices)} devices")
        for device_id, device in devices.items():
            print(f"Device ID: {device_id}")
            print(f"Device Type: {device.device_type}")

asyncio.run(test_connection())
```

## Troubleshooting

### Cannot Find Device Access Point
- Make sure the device is in setup mode
- Try resetting the device again
- Move closer to the device

### WiFi Configuration Fails
- Verify the WiFi credentials are correct
- Make sure the security type is correct
- Check if the device is still in setup mode

### Provisioning Fails
- Verify the device's IP address is correct
- Make sure the device is connected to your WiFi
- Try both HTTP and HTTPS with the `--use-https` flag

### Connection Test Fails
- Verify the credentials in the file match what was provisioned
- Check if the device is reachable (ping the IP address)
- Make sure the device hasn't gone into sleep mode 

## Factory Reset

This section explains how to use the factory reset functionality in the asyncmiele library to reset Miele devices to their factory default settings.

### Overview

The factory reset functionality allows you to:

1. Reset a Miele device to factory default settings
2. Wait for the device to enter setup mode after reset
3. Discover and list devices in setup mode
4. Provide instructions for reconfiguring the device after reset

### When to Use Factory Reset

Factory reset should be used when:

- The device is not responding to normal commands
- You want to clear all device settings and start fresh
- You're experiencing connectivity issues that can't be resolved
- You're preparing to transfer ownership of the device
- The device is in an inconsistent state

### Requirements

To perform a factory reset, you'll need:

1. The IP address or hostname of the device
2. Valid security credentials (group_id and group_key)
3. Network connectivity to the device

### Using the Factory Reset Script

The library includes a dedicated script for performing factory resets:

```bash
# Basic usage with config file
./scripts/device_factory_reset.py --config examples/connection_config.json

# Reset a specific device from the config file
./scripts/device_factory_reset.py --config examples/connection_config.json --device-id 000123456789

# Reset using direct connection parameters
./scripts/device_factory_reset.py --host 192.168.1.100 --group-id 11223344556677889900aabbccddeeff --group-key 00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff

# Skip the confirmation prompt
./scripts/device_factory_reset.py --config examples/connection_config.json --force

# Don't wait for the device to enter setup mode after reset
./scripts/device_factory_reset.py --config examples/connection_config.json --no-wait

# Change the timeout for waiting for setup mode
./scripts/device_factory_reset.py --config examples/connection_config.json --timeout 180.0

# Just discover and list devices on the network
./scripts/device_factory_reset.py --discover
```

### Command Line Arguments

| Argument | Description |
|----------|-------------|
| `--config` | Path to configuration file with device profiles |
| `--device-id` | Device ID to reset (if using config file with multiple devices) |
| `--host` | Device IP address or hostname (alternative to config file) |
| `--group-id` | Group ID in hex (required if using --host) |
| `--group-key` | Group Key in hex (required if using --host) |
| `--no-wait` | Don't wait for the device to enter setup mode after reset |
| `--timeout` | Timeout in seconds to wait for device to enter setup mode (default: 120) |
| `--force` | Skip confirmation prompt |
| `--discover` | Just discover and list Miele devices on the network |
| `--debug` | Enable debug logging |

### Configuration File Format

The configuration file should be in JSON format and contain device information:

```json
{
  "devices": [
    {
      "id": "000123456789",
      "host": "192.168.1.100",
      "group_id": "11223344556677889900aabbccddeeff",
      "group_key": "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
    }
  ]
}
```

### Reset Process

The reset process follows these steps:

1. **Confirmation**: Unless `--force` is used, the script will ask for confirmation before proceeding
2. **Connection**: The script establishes a connection to the device
3. **MAC Address Caching**: The script attempts to cache the device's MAC address to aid in discovery after reset
4. **Reset Command**: The script sends the factory reset command to the device
5. **Waiting for Setup Mode**: Unless `--no-wait` is used, the script waits for the device to enter setup mode
6. **Discovery**: After reset, the script performs a discovery to find devices in setup mode
7. **Reconfiguration Instructions**: The script provides instructions for reconfiguring the device

### After Reset

After a factory reset, the device will:

1. Clear all configuration settings
2. Enter setup mode (access point mode)
3. Need to be reconfigured with WiFi credentials and security settings

To reconfigure the device, use the MieleSetupClient:

```bash
python -m asyncmiele.scripts.configure_device_wifi --help
```

### Troubleshooting

If the factory reset fails or the device doesn't enter setup mode:

1. **Check Physical Access**: Some devices may require physical button presses to confirm the reset
2. **Check Documentation**: Refer to the device manual for model-specific reset procedures
3. **Try Manual Reset**: Most Miele devices have a physical reset button or procedure
4. **Check Network**: Ensure you have network connectivity to the device before reset
5. **Update Credentials**: Ensure you're using the correct group_id and group_key
6. **Increase Timeout**: Try increasing the timeout with `--timeout` for slower devices

### Caution

Factory reset is an irreversible operation. All device settings will be lost and will need to be reconfigured. Always attempt less drastic troubleshooting methods before performing a factory reset. ## Acknowledgments

This project is based on reverse-engineering efforts of the Miele@Home protocol and inspired by the [home-assistant-miele-mobile](https://github.com/thuxnder/home-assistant-miele-mobile) project. It has been refactored to be independent of Home Assistant and provide a clean, asynchronous API.

## License

MIT

#### Wait for Conditions
