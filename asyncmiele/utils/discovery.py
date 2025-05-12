"""
Discovery utilities for finding Miele devices on the local network.
"""

from __future__ import annotations

import asyncio
import socket
from typing import List, Dict, Any, Optional, AsyncIterator

import aiohttp

from asyncmiele.exceptions.network import NetworkException
from asyncmiele.api.client import MieleClient



async def discover_devices(timeout: float = 5.0) -> List[Dict[str, Any]]:
    """
    Discover Miele devices on the local network.
    
    This function uses UPnP/SSDP to discover Miele devices that
    support the XKM3100W or built-in WiFi module.
    
    Args:
        timeout: Discovery timeout in seconds
        
    Returns:
        List of discovered devices with their host address and other info
        
    Raises:
        NetworkException: If the discovery process fails
    """
    # SSDP discovery message for Miele devices
    SSDP_DISCOVER = (
        'M-SEARCH * HTTP/1.1\r\n'
        'HOST: 239.255.255.250:1900\r\n'
        'MAN: "ssdp:discover"\r\n'
        'ST: urn:miele-com:device\r\n'  # Search target for Miele devices
        'MX: 2\r\n'                      # Maximum wait time
        '\r\n'
    )
    
    try:
        # Create multicast socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(timeout)
        
        # Send discovery message
        sock.sendto(SSDP_DISCOVER.encode(), ('239.255.255.250', 1900))
        
        # Response collection
        responses = []
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                data, addr = sock.recvfrom(1024)
                responses.append((data.decode(), addr))
            except socket.timeout:
                break
                
        # Process and extract device information
        devices = []
        for response, addr in responses:
            device_info = {
                'host': addr[0],  # IP address
            }
            
            # Extract more details from response headers
            for line in response.splitlines():
                if line.startswith('SERVER:'):
                    device_info['server'] = line[8:].strip()
                elif line.startswith('LOCATION:'):
                    device_info['location'] = line[10:].strip()
                    
            # Only add devices that are likely Miele devices
            if 'server' in device_info and 'Miele' in device_info['server']:
                devices.append(device_info)
                
        return devices
        
    except Exception as e:
        raise NetworkException(f"Device discovery failed: {str(e)}")
    finally:
        try:
            sock.close()
        except:
            pass


async def get_device_info(host: str, timeout: float = 5.0) -> Dict[str, Any]:
    """
    Get basic device information without authentication.
    
    This retrieves publicly available information about the device
    before registration/authentication.
    
    Args:
        host: Device IP address or hostname
        timeout: Request timeout in seconds
        
    Returns:
        Dictionary of device information
        
    Raises:
        NetworkException: If the request fails
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://{host}/api/v1/device",
                timeout=timeout
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {'error': f'HTTP Error: {response.status}'}
    except aiohttp.ClientError as e:
        raise NetworkException(f"Failed to retrieve device info: {str(e)}")

# ---------------------------------------------------------------------------
# Convenience shortcut (Phase-3)
# ---------------------------------------------------------------------------

async def auto_clients(
    group_id_hex: str,
    group_key_hex: str,
    *,
    timeout: float = 5.0,
) -> AsyncIterator[MieleClient]:
    """Discover devices and yield ready :class:`asyncmiele.api.client.MieleClient` instances.

    Example
    -------
    >>> async for cli in auto_clients(gid, gkey):
    ...     print(await cli.get_devices())
    """

    devices = await discover_devices(timeout)
    for dev in devices:
        host = dev.get("host")
        if host:
            yield MieleClient.from_hex(host, group_id_hex, group_key_hex, timeout=timeout)