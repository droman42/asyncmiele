# AsyncMiele

An asynchronous Python client for Miele@Home devices.

This library provides a simple, asynchronous interface to communicate with Miele appliances that support the Miele@Home protocol over local network (e.g., via XKM3100W module or built-in WiFi).

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

### Connecting to Devices

Once you have the credentials, you can connect to your device:

```python
import asyncio
from asyncmiele import MieleClient

async def get_device_info():
    # Create client with your stored credentials
    client = MieleClient(
        host="192.168.1.123",
        group_id=bytes.fromhex("your_group_id"),
        group_key=bytes.fromhex("your_group_key")
    )
    
    # Get all devices
    devices = await client.get_devices()
    
    for device_id, device in devices.items():
        print(f"Device ID: {device_id}")
        print(f"Name: {device.name}")
        print(f"Status: {device.state.status}")
        
        if device.state.program_phase:
            print(f"Program: {device.state.program_type}")
            print(f"Phase: {device.state.program_phase}")
            
        if device.state.remaining_time:
            print(f"Remaining time: {device.state.remaining_time} seconds")
            
    # Get updates for a specific device
    device = await client.get_device("your_device_id")
    state = await client.get_device_state("your_device_id")

asyncio.run(get_device_info())
```

### Error Handling

The library provides detailed exception classes for proper error handling:

```python
import asyncio
from asyncmiele import MieleClient
from asyncmiele.exceptions.network import ConnectionError, TimeoutError
from asyncmiele.exceptions.api import DeviceNotFoundError

async def handle_errors():
    try:
        client = MieleClient(
            host="192.168.1.123",
            group_id=bytes.fromhex("your_group_id"),
            group_key=bytes.fromhex("your_group_key")
        )
        
        device = await client.get_device("non_existent_id")
        
    except ConnectionError as e:
        print(f"Connection failed: {e}")
    except TimeoutError as e:
        print(f"Request timed out: {e}")
    except DeviceNotFoundError as e:
        print(f"Device not found: {e}")

asyncio.run(handle_errors())
```

## Acknowledgments

This project is based on reverse-engineering efforts of the Miele@Home protocol and inspired by the [home-assistant-miele-mobile](https://github.com/username/home-assistant-miele-mobile) project. It has been refactored to be independent of Home Assistant and provide a clean, asynchronous API.

## License

MIT
