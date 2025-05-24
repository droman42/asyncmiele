"""
AsyncMiele: Async client for Miele home appliances.
"""

__version__ = "0.1.0"
__author__ = "droman42"

from asyncmiele.api import MieleClient, MieleSetupClient
from asyncmiele.capabilities import DeviceCapability
from asyncmiele.models.device_profile import DeviceProfile
from asyncmiele.models.credentials import MieleCredentials
from asyncmiele.appliance import Appliance
from asyncmiele.connection import ConnectionManager, ConnectionPool, ConnectionHealthMonitor, DeviceResetter
from asyncmiele.connection.health import ConnectionState

__all__ = [
    'MieleClient',
    'MieleSetupClient',
    'DeviceCapability',
    'DeviceProfile',
    'MieleCredentials',
    'Appliance',
    'ConnectionManager',
    'ConnectionPool',
    'ConnectionHealthMonitor',
    'DeviceResetter',
    'ConnectionState',
]

from asyncmiele.api.client import MieleClient
from asyncmiele.models.device import MieleDevice, DeviceState, DeviceIdentification
from asyncmiele.models.response import MieleResponse
from asyncmiele.exceptions import MieleException
from asyncmiele.exceptions.api import APIException, DeviceNotFoundError, DecryptionError, ParseError
from asyncmiele.exceptions.network import NetworkException, NetworkConnectionError, NetworkTimeoutError, ResponseError
from asyncmiele.exceptions.auth import AuthenticationException, InvalidCredentialsError, AuthorizationError, RegistrationError
from asyncmiele.utils.crypto import generate_credentials
from asyncmiele.utils.discovery import discover_devices, get_device_info
from asyncmiele.enums import Status as StatusEnum, ProgramPhase as ProgramPhaseEnum, ProgramId as ProgramIdEnum, DeviceType as DeviceTypeEnum

# Phase-14 re-exports -------------------------------------------------------
from asyncmiele.programs import ProgramCatalog, build_dop2_selection
from asyncmiele.dop2.models import ConsumptionStats, TariffConfig
from asyncmiele.subscription import SubscriptionManager

async def easy_setup(host: str):
    """
    Set up a new client with a Miele device.
    
    Args:
        host: IP address or hostname of the Miele device
        
    Returns:
        Tuple of (device_id, group_id, group_key) for storing in configuration
    """
    return await MieleClient.easy_setup(host)
