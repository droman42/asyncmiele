"""
Utilities for Miele device provisioning and setup.

This module provides functions for device discovery, key generation,
and provisioning of Miele devices.
"""

import secrets
from typing import Tuple, Dict, Any, Optional, List, Union
import socket
import asyncio
import logging
import ipaddress
import subprocess
import platform
import re
import sys
from asyncmiele.models.credentials import MieleCredentials
from asyncmiele.models.network_config import MieleNetworkConfig
from asyncmiele.exceptions.network import NetworkConnectionError
from asyncmiele.exceptions.setup import AccessPointConnectionError

logger = logging.getLogger(__name__)


def generate_credentials() -> MieleCredentials:
    """
    Generate random GroupID and GroupKey credentials for device provisioning.
    
    Returns:
        MieleCredentials: Newly generated credentials
    """
    return MieleCredentials.generate_random()


def _get_local_subnets() -> List[str]:
    """
    Get a list of local subnets using platform-specific methods.
    
    Returns:
        List of subnets in CIDR notation
    """
    subnets = []
    
    system = platform.system().lower()
    
    if system == 'linux':
        # Try to use ip command on Linux
        try:
            output = subprocess.check_output(['ip', '-4', 'addr', 'show']).decode('utf-8')
            # Extract IP/mask pairs using regex
            matches = re.finditer(r'inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)', output)
            for match in matches:
                ip = match.group(1)
                mask = int(match.group(2))
                # Skip loopback
                if ip.startswith('127.'):
                    continue
                # Convert to network address
                network = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
                subnets.append(str(network))
        except (subprocess.SubprocessError, FileNotFoundError):
            # Fallback if ip command fails
            pass
    
    # Fallback method using socket
    if not subnets:
        try:
            # Get hostname and resolve it to get local IP
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            
            # Skip loopback
            if not ip.startswith('127.'):
                # Assume a /24 subnet as fallback
                subnet = ip.rsplit('.', 1)[0] + '.0/24'
                subnets.append(subnet)
        except socket.error:
            pass
    
    # Last resort: scan common private subnets
    if not subnets:
        logger.warning("Could not detect local subnets, using common private subnets")
        subnets = ["192.168.1.0/24", "192.168.0.0/24", "10.0.0.0/24", "172.16.0.0/24"]
    
    return subnets


async def scan_for_miele_devices(
    subnet: Optional[str] = None,
    timeout: float = 2.0,
    ports: List[int] = [80, 443],
) -> Dict[str, Dict[str, Any]]:
    """
    Scan the network for Miele devices.
    
    Args:
        subnet: Subnet to scan in CIDR notation (e.g., '192.168.1.0/24')
                If None, all local subnets will be scanned
        timeout: Timeout for connection attempts in seconds
        ports: Ports to check for Miele devices
        
    Returns:
        Dictionary of discovered devices with IP as key and device info as value
    """
    discovered_devices = {}
    
    # Determine subnets to scan
    subnets_to_scan = []
    if subnet:
        subnets_to_scan.append(subnet)
    else:
        subnets_to_scan = _get_local_subnets()
    
    if not subnets_to_scan:
        logger.warning("No subnets found for scanning")
        return discovered_devices
        
    logger.info(f"Scanning subnets: {subnets_to_scan}")
    
    # Scan all subnets
    for subnet_cidr in subnets_to_scan:
        network = ipaddress.IPv4Network(subnet_cidr)
        # Create a list of hosts to scan (skip network and broadcast addresses)
        hosts = [str(ip) for ip in network.hosts()]
        
        # Create tasks for each host
        tasks = []
        for host in hosts:
            for port in ports:
                tasks.append(check_miele_device(host, port, timeout))
                
        # Run tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, dict) and 'ip' in result:
                discovered_devices[result['ip']] = result
                
    return discovered_devices


async def check_miele_device(host: str, port: int, timeout: float) -> Optional[Dict[str, Any]]:
    """
    Check if a host:port combination is a Miele device.
    
    Args:
        host: IP address to check
        port: Port to check
        timeout: Connection timeout in seconds
        
    Returns:
        Device information dictionary if a Miele device is found, None otherwise
    """
    try:
        # First check if the port is open
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )
        
        try:
            # Try to detect if this is a Miele device
            # Send a simple HTTP request to check headers
            writer.write(b"HEAD / HTTP/1.1\r\nHost: " + host.encode() + b"\r\n\r\n")
            await writer.drain()
            
            # Read response
            response = await asyncio.wait_for(reader.read(1024), timeout=timeout)
            
            # Check if it's a Miele device based on response
            response_str = response.decode('utf-8', errors='ignore')
            
            is_miele = False
            device_type = None
            
            # Check for Miele-specific patterns in the response
            if "Miele" in response_str or "XGW" in response_str:
                is_miele = True
                
            # Try to determine if it's in setup mode
            setup_mode = False
            if "Miele@home" in response_str:
                setup_mode = True
                
            if is_miele:
                return {
                    "ip": host,
                    "port": port,
                    "is_miele_device": True,
                    "setup_mode": setup_mode,
                    "device_type": device_type,
                    "raw_response": response_str[:200]  # Include part of the response for debugging
                }
        finally:
            writer.close()
            await writer.wait_closed()
            
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError) as e:
        # Connection failed or timed out
        return None
    
    return None


async def detect_device_id(host: str, timeout: float = 5.0) -> Optional[str]:
    """
    Attempt to detect a device ID from a Miele device.
    
    This tries to access the Devices endpoint to find the device ID.
    Note that this may not work for devices in setup mode.
    
    Args:
        host: Device IP address or hostname
        timeout: Connection timeout in seconds
        
    Returns:
        Device ID if found, None otherwise
    """
    try:
        # Create a simple HTTP request to the Devices endpoint
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, 80),
            timeout=timeout
        )
        
        try:
            # Send request
            writer.write(b"GET /Devices HTTP/1.1\r\nHost: " + host.encode() + b"\r\n\r\n")
            await writer.drain()
            
            # Read response
            response = await asyncio.wait_for(reader.read(4096), timeout=timeout)
            response_str = response.decode('utf-8', errors='ignore')
            
            # Look for device ID patterns in the response
            import re
            # Try to find a 12-digit device ID
            match = re.search(r'"([0-9]{12})"', response_str)
            if match:
                return match.group(1)
                
            return None
            
        finally:
            writer.close()
            await writer.wait_closed()
            
    except Exception as e:
        logger.debug(f"Failed to detect device ID for {host}: {str(e)}")
        return None


def detect_setup_mode_ssid() -> List[str]:
    """
    Detect Miele setup mode SSIDs in available WiFi networks.
    
    This function uses platform-specific methods to scan for WiFi networks
    and identify those that match Miele's setup mode pattern.
    
    Returns:
        List of Miele setup mode SSIDs
    """
    miele_ssids = []
    system = platform.system().lower()
    
    try:
        if system == 'linux':
            # Try to use nmcli on Linux
            try:
                output = subprocess.check_output(['nmcli', '-t', '-f', 'SSID', 'device', 'wifi', 'list']).decode('utf-8')
                for line in output.splitlines():
                    ssid = line.strip()
                    if ssid.startswith('Miele@home'):
                        miele_ssids.append(ssid)
            except (subprocess.SubprocessError, FileNotFoundError):
                # Try iwlist as fallback
                try:
                    # Find wireless interfaces
                    iw_output = subprocess.check_output(['iwconfig']).decode('utf-8', errors='ignore')
                    wireless_interfaces = []
                    for line in iw_output.splitlines():
                        if 'IEEE 802.11' in line:
                            wireless_interfaces.append(line.split()[0])
                    
                    # Scan networks on each interface
                    for interface in wireless_interfaces:
                        scan_output = subprocess.check_output(['sudo', 'iwlist', interface, 'scan']).decode('utf-8', errors='ignore')
                        for ssid_match in re.finditer(r'ESSID:"([^"]+)"', scan_output):
                            ssid = ssid_match.group(1)
                            if ssid.startswith('Miele@home'):
                                miele_ssids.append(ssid)
                except (subprocess.SubprocessError, FileNotFoundError):
                    logger.warning("Could not scan for WiFi networks using iwlist")
                    
        elif system == 'darwin':  # macOS
            try:
                # Use airport utility on macOS
                output = subprocess.check_output(['/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport', '-s']).decode('utf-8')
                for line in output.splitlines()[1:]:  # Skip header line
                    parts = line.split()
                    if len(parts) >= 1 and parts[0].startswith('Miele@home'):
                        miele_ssids.append(parts[0])
            except (subprocess.SubprocessError, FileNotFoundError):
                logger.warning("Could not scan for WiFi networks on macOS")
                
        elif system == 'windows':
            try:
                # Use netsh on Windows
                output = subprocess.check_output(['netsh', 'wlan', 'show', 'networks']).decode('utf-8', errors='ignore')
                for ssid_match in re.finditer(r'SSID\s+\d+\s+:\s+([^\r\n]+)', output):
                    ssid = ssid_match.group(1).strip()
                    if ssid.startswith('Miele@home'):
                        miele_ssids.append(ssid)
            except (subprocess.SubprocessError, FileNotFoundError):
                logger.warning("Could not scan for WiFi networks on Windows")
    
    except Exception as e:
        logger.error(f"Error scanning for WiFi networks: {str(e)}")
    
    return miele_ssids


def connect_to_miele_ap(ssid: str, password: Optional[str] = None) -> bool:
    """
    Connect to a Miele device's access point.
    
    This function uses platform-specific methods to connect to the specified WiFi network.
    Note that this requires appropriate permissions to change network connections.
    
    Args:
        ssid: WiFi network SSID to connect to
        password: WiFi password (None for open networks)
        
    Returns:
        True if connection was successful, False otherwise
        
    Raises:
        AccessPointConnectionError: If the connection fails
    """
    logger.info(f"Attempting to connect to Miele access point: {ssid}")
    
    system = platform.system().lower()
    success = False
    
    try:
        if system == 'linux':
            # Try nmcli on Linux
            try:
                if password:
                    cmd = ['nmcli', 'device', 'wifi', 'connect', ssid, 'password', password]
                else:
                    cmd = ['nmcli', 'device', 'wifi', 'connect', ssid]
                    
                subprocess.check_call(cmd)
                success = True
            except subprocess.SubprocessError as e:
                logger.error(f"Failed to connect using nmcli: {str(e)}")
                
        elif system == 'darwin':  # macOS
            # For macOS, we need to use airport or networksetup
            try:
                # First find the WiFi interface name
                interface_output = subprocess.check_output(['networksetup', '-listallhardwareports']).decode('utf-8')
                wifi_interface = None
                
                for i, line in enumerate(interface_output.splitlines()):
                    if 'Wi-Fi' in line or 'AirPort' in line:
                        # The next line should contain the interface name
                        interface_match = re.search(r'Device:\s+(\w+)', interface_output.splitlines()[i+1])
                        if interface_match:
                            wifi_interface = interface_match.group(1)
                            break
                
                if wifi_interface:
                    if password:
                        subprocess.check_call(['networksetup', '-setairportnetwork', wifi_interface, ssid, password])
                    else:
                        subprocess.check_call(['networksetup', '-setairportnetwork', wifi_interface, ssid])
                    success = True
                else:
                    logger.error("Could not find WiFi interface on macOS")
                    
            except subprocess.SubprocessError as e:
                logger.error(f"Failed to connect using networksetup: {str(e)}")
                
        elif system == 'windows':
            # For Windows, use netsh
            try:
                # Create a temporary profile XML file
                import tempfile
                
                profile_xml = f"""<?xml version="1.0"?>
                <WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
                    <name>{ssid}</name>
                    <SSIDConfig>
                        <SSID>
                            <name>{ssid}</name>
                        </SSID>
                    </SSIDConfig>
                    <connectionType>ESS</connectionType>
                    <connectionMode>manual</connectionMode>
                    <MSM>
                        <security>
                            <authEncryption>
                                <authentication>{'open' if not password else 'WPA2PSK'}</authentication>
                                <encryption>{'none' if not password else 'AES'}</encryption>
                                <useOneX>false</useOneX>
                            </authEncryption>
                            {'<sharedKey><keyType>passPhrase</keyType><protected>false</protected><keyMaterial>' + password + '</keyMaterial></sharedKey>' if password else ''}
                        </security>
                    </MSM>
                </WLANProfile>"""
                
                with tempfile.NamedTemporaryFile(suffix='.xml', delete=False) as profile_file:
                    profile_path = profile_file.name
                    profile_file.write(profile_xml.encode('utf-8'))
                
                # Add the profile and connect
                subprocess.check_call(['netsh', 'wlan', 'add', 'profile', 'filename=' + profile_path])
                subprocess.check_call(['netsh', 'wlan', 'connect', 'name=' + ssid])
                
                # Clean up
                import os
                os.unlink(profile_path)
                
                success = True
                
            except subprocess.SubprocessError as e:
                logger.error(f"Failed to connect using netsh: {str(e)}")
        
        else:
            logger.error(f"Unsupported platform: {system}")
            
    except Exception as e:
        logger.error(f"Error connecting to Miele access point: {str(e)}")
    
    if not success:
        logger.error(f"Failed to connect to Miele access point {ssid}")
        raise AccessPointConnectionError(f"Failed to connect to Miele access point {ssid}")
    
    logger.info(f"Successfully connected to Miele access point: {ssid}")
    return success


def get_default_ap_password(ssid: str) -> Optional[str]:
    """
    Get the default password for a Miele access point based on its SSID.
    
    According to Miele's documentation, different device generations use different
    authentication methods:
    - If the SSID is just "Miele@home", the password is "secured-by-tls"
    - If the SSID has a suffix like "Miele@home-TAA1234", the password is the device's 
      serial number shown on its sticker
    
    Args:
        ssid: The SSID of the Miele access point
        
    Returns:
        Default password if it can be determined, None otherwise
    """
    if ssid == "Miele@home":
        return "secured-by-tls"
    
    # For newer devices, we can't determine the password automatically
    # as it's the device's serial number
    if ssid.startswith("Miele@home-"):
        logger.info(f"The password for {ssid} is likely the device's serial number shown on its sticker")
        return None
    
    return None 