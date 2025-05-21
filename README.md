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

## Acknowledgments

This project is based on reverse-engineering efforts of the Miele@Home protocol and inspired by the [home-assistant-miele-mobile](https://github.com/thuxnder/home-assistant-miele-mobile) project. It has been refactored to be independent of Home Assistant and provide a clean, asynchronous API.

## License

MIT

#### Wait for Conditions
