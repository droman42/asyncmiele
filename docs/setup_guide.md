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

Factory reset is an irreversible operation. All device settings will be lost and will need to be reconfigured. Always attempt less drastic troubleshooting methods before performing a factory reset. 