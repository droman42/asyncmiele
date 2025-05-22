# Connection Optimization Guide

This document explains how to use the connection optimization features in the asyncmiele library to enhance reliability and performance when working with Miele devices.

## Overview

The connection optimization module provides several key components:

1. **ConnectionManager**: Central manager for handling multiple device connections with optimized performance
2. **ConnectionPool**: Manages connection reuse and efficient allocation
3. **ConnectionHealthMonitor**: Monitors connection health and detects issues
4. **DeviceResetter**: Handles device reset detection and recovery

These components work together to provide:

- Efficient handling of multiple device connections
- Automatic connection recovery
- Connection health monitoring
- Graceful handling of device resets
- Intelligent retry mechanisms

## Basic Usage

### Setting up the Connection Manager

```python
from asyncmiele import ConnectionManager, DeviceProfile

# Create a connection manager
connection_manager = ConnectionManager(
    max_connections=10,       # Maximum concurrent connections
    connection_timeout=10.0,  # Connection timeout in seconds
    health_check_interval=60.0,  # Health check interval in seconds
    retry_count=3,            # Number of retries for failed operations
    retry_delay=2.0           # Delay between retries in seconds
)

# Use as async context manager
async with connection_manager:
    # Get a client for a device
    client = await connection_manager.get_client(device_id, profile)
    
    # Use the client...
    result = await connection_manager.execute_with_retry(
        device_id,
        lambda: client.get_device_state(device_id)
    )
```

### Automatic Retry and Recovery

The connection manager provides automatic retry and recovery for operations:

```python
# Execute an operation with automatic retry
try:
    result = await connection_manager.execute_with_retry(
        device_id,
        lambda: client.some_operation(device_id)
    )
    print(f"Operation succeeded: {result}")
except ConnectionLostError as e:
    print(f"Connection lost and could not be recovered: {e}")
```

### Connection Health Monitoring

The health monitor tracks connection health and can notify you of state changes:

```python
# Get the health monitor
health_monitor = connection_manager.get_health_monitor()

# Register a callback for state changes
async def on_state_change(device_id, new_state):
    print(f"Connection state for {device_id} changed to {new_state}")
    
    if new_state == ConnectionState.UNHEALTHY:
        # Take recovery action
        pass

# Register the callback
health_monitor.register_state_callback(device_id, on_state_change)
```

## Handling Device Resets

The `DeviceResetter` class helps manage device reset operations:

```python
from asyncmiele import DeviceResetter

# Create a device resetter
resetter = DeviceResetter()

# Detect if a device has been reset
is_reset = await resetter.detect_factory_reset(client, device_id)

if is_reset:
    # Recover from reset
    success, new_client = await resetter.recover_from_reset(device_id, profile)
    if success:
        print("Successfully recovered device")
else:
    # Optionally initiate a reset
    # await resetter.initiate_reset(client, device_id)
```

## Advanced Usage

### Custom Health Checks

You can define custom health checks for devices:

```python
async def custom_health_check():
    try:
        # Perform a custom health check operation
        await client.get_device_ident(device_id)
        return True
    except Exception:
        return False

# Register the custom health check
health_monitor.register_health_check(device_id, custom_health_check)
```

### Connection Pool Management

For fine-grained control over the connection pool:

```python
# Get the connection pool
pool = connection_manager.get_connection_pool()

# Get pool statistics
print(f"Total connections: {len(pool)}")
print(f"Active connections: {pool.active_connections}")
print(f"Idle connections: {pool.idle_connections}")
```

## Configuration Example

A typical configuration file might look like:

```json
{
  "devices": [
    {
      "id": "000123456789",
      "host": "192.168.1.100",
      "group_id": "11223344556677889900aabbccddeeff",
      "group_key": "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
    }
  ],
  "connection_settings": {
    "max_connections": 5,
    "connection_timeout": 10.0,
    "health_check_interval": 30.0,
    "retry_count": 3,
    "retry_delay": 2.0
  }
}
```

## Best Practices

1. **Use the ConnectionManager**: Always use the ConnectionManager for optimal connection handling
2. **Wrap operations in execute_with_retry**: This provides automatic retry and recovery
3. **Monitor connection health**: Register health state callbacks to be notified of issues
4. **Handle device resets gracefully**: Use the DeviceResetter to recover from reset states
5. **Configure timeouts appropriately**: Set timeouts based on your network conditions

## Error Handling

The connection module provides specific exceptions for different error scenarios:

- `ConnectionLostError`: Connection was lost and could not be reconnected
- `ReconnectionError`: Failed to reconnect to a device
- `ConnectionPoolExhaustedError`: No more connections available in the pool
- `DeviceResetError`: Error during device reset operations
- `ConnectionHealthError`: Error in connection health monitoring
- `DeviceSleepError`: Device is in sleep mode and cannot process commands

Example error handling:

```python
from asyncmiele.exceptions.connection import ConnectionLostError, ReconnectionError

try:
    result = await connection_manager.execute_with_retry(device_id, operation)
except ConnectionLostError as e:
    print(f"Connection permanently lost: {e}")
except ReconnectionError as e:
    print(f"Failed to reconnect: {e}")
```

## Performance Considerations

- The connection pool automatically manages connection reuse for optimal performance
- Health checks are performed asynchronously to minimize impact on operations
- The connection manager uses exponential backoff for retries to avoid overwhelming devices
- Idle connections are automatically closed to free up resources

## Example Application

See `scripts/optimized_connection_example.py` for a complete example of using the connection optimization features. Run it with:

```bash
python scripts/optimized_connection_example.py --config examples/connection_config.json --example monitor
```

For testing reset functionality:

```bash
python scripts/optimized_connection_example.py --config examples/connection_config.json --example reset --device-id 000123456789
``` 