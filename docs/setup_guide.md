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

This section explains how to use the factory reset functionality in the asyncmiele library to reset Miele devices to their factory default settings using the DOP2 protocol.

### Overview

The factory reset functionality uses the **DOP2 protocol with XKM (eXtended Key Management) commands** to perform device resets. This approach is universal and works across all Miele device types that support factory reset functionality.

The reset process attempts multiple methods:

1. **Universal XKM FactorySettings command** - Works on all device types (primary method)
2. **Device-specific SF (Setting Function) values** - Type-specific fallback method
3. **Multiple DOP2 unit/attribute combinations** - For maximum compatibility

### Key Features

- **Universal compatibility**: XKM commands work across all device types
- **Automatic fallback**: Falls back to device-specific methods if needed
- **DOP2 protocol**: Uses proper encrypted communication protocol
- **Device type detection**: Automatically detects device type for optimal reset method
- **Recovery assistance**: Helps discover and reconfigure devices after reset

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
4. Device must be powered on and in normal operating mode

### Using the Factory Reset Script

The library includes a dedicated script for performing factory resets using the DOP2 XKM protocol:

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

# Enable debug logging to see DOP2 protocol details
./scripts/device_factory_reset.py --config examples/connection_config.json --debug

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
| `--debug` | Enable debug logging (shows DOP2 protocol details) |

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

The DOP2 XKM reset process follows these steps:

1. **Confirmation**: Unless `--force` is used, the script will ask for confirmation before proceeding
2. **Connection**: The script establishes a connection to the device
3. **Device Detection**: The script detects device type and caches MAC address for recovery
4. **XKM Reset Command**: The script sends XKM FactorySettings command via DOP2 protocol
5. **Fallback Methods**: If XKM fails, tries device-specific SF values
6. **Multiple Endpoints**: Attempts various DOP2 unit/attribute combinations
7. **Waiting for Setup Mode**: Unless `--no-wait` is used, the script waits for the device to enter setup mode
8. **Discovery**: After reset, the script performs a discovery to find devices in setup mode
9. **Reconfiguration Instructions**: The script provides instructions for reconfiguring the device

### Technical Details

#### XKM (eXtended Key Management) Commands

The primary reset method uses XKM FactorySettings command (value: 2) sent via DOP2 protocol:

- **Unit/Attribute combinations tried**: (1,1), (1,2), (1,100), (2,1)
- **Payload format**: 16-bit XKM request type, padded for AES encryption
- **Protocol**: Encrypted DOP2 with HMAC signature

#### Device-Specific Fallbacks

If XKM commands fail, the script attempts device-specific SF values:

| Device Type | SF Value | Description |
|-------------|----------|-------------|
| Washing Machines | 12196 | Washer_FactoryReset |
| Tumble Dryers | 16001 | Dryer_FactoryDefault |
| Dishwashers | XKM only | No specific SF value |
| Ovens/Ranges | XKM only | No specific SF value |
| Induction Hobs/Cooktops | XKM only | Limited connectivity - often no remote reset |
| Other devices | XKM only | Universal approach |

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

#### Reset Command Fails

If the factory reset command fails:

1. **Check Device State**: Ensure device is powered on and in normal operating mode
2. **Verify Credentials**: Confirm group_id and group_key are correct
3. **Check Network**: Ensure network connectivity to the device
4. **Device Support**: Verify device supports remote factory reset
5. **Manual Reset**: Try physical reset button if available

#### Special Considerations for Induction Hobs

Induction hobs and cooktops typically have very limited connectivity features compared to other Miele appliances:

1. **Limited Remote Control**: Most induction hobs don't support remote factory reset
2. **Manual Reset Required**: Factory reset typically requires using the physical control panel
3. **Network Features**: May only support basic network connectivity for monitoring
4. **Manual Reset Procedure**:
   - Access the device's settings menu on the control panel
   - Navigate to "Settings", "Configuration", or "Network" options
   - Look for "Reset", "Factory Settings", or "Network Reset"
   - Follow the on-screen instructions
   - Some models may require holding specific button combinations
   - Consult your device manual for model-specific instructions

#### Device Doesn't Enter Setup Mode

If the device doesn't enter setup mode after reset:

1. **Wait Longer**: Some devices take several minutes to complete reset
2. **Check Display**: Look for reset confirmation prompts on device display
3. **Manual Confirmation**: Some devices require manual confirmation
4. **Power Cycle**: Try turning device off and on again
5. **Physical Reset**: Use device's physical reset procedure

#### Discovery Issues

If you can't find the device after reset:

1. **Network Scanning**: Try manual network scanning for new access points
2. **MAC Address**: Look for the cached MAC address in WiFi networks
3. **Different Network**: Device may create its own WiFi network
4. **Timing**: Wait a few minutes and try discovery again
5. **Physical Proximity**: Move closer to the device

### Caution

**Factory reset is an irreversible operation.** All device settings will be lost and will need to be reconfigured. Always attempt less drastic troubleshooting methods before performing a factory reset.

**Important Notes:**
- Some devices may require manual confirmation via display interface
- Reset process may take several minutes to complete
- Device will disconnect from current WiFi network during reset
- All custom settings, programs, and network configurations will be lost
- Device must be reconfigured before it can be used again 