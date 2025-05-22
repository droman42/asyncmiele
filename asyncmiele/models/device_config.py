"""
Device configuration models for Miele devices.
"""

import re
from typing import Optional, ClassVar
from pydantic import BaseModel, Field, field_validator, model_validator

from asyncmiele.models.credentials import MieleCredentials


class MieleDeviceConfig(BaseModel):
    """
    Configuration for a Miele device including connection parameters.
    """
    # Regular expression for validating device IDs
    DEVICE_ID_PATTERN: ClassVar[re.Pattern] = re.compile(r'^[0-9]{12}$')
    
    # Device identifier (12-digit string)
    device_id: str = Field(
        description="Miele device identifier (12 digits)"
    )
    
    # Host address (IP or hostname)
    host: str = Field(
        description="IP address or hostname of the device"
    )
    
    # Authentication credentials
    credentials: MieleCredentials = Field(
        description="Authentication credentials for the device"
    )
    
    # Optional device name for user-friendly identification
    name: Optional[str] = Field(
        default=None,
        description="User-friendly name for the device"
    )
    
    # Optional device type (will be auto-detected if not provided)
    device_type: Optional[str] = Field(
        default=None,
        description="Device type (e.g., 'Oven', 'Dishwasher', etc.)"
    )
    
    # Connection timeout in seconds
    timeout: float = Field(
        default=5.0,
        description="Connection timeout in seconds"
    )
    
    # Feature flags based on device capabilities
    supports_dop2: bool = Field(
        default=True,
        description="Whether the device supports DOP2 protocol"
    )
    
    supports_program_catalog: bool = Field(
        default=True,
        description="Whether the device supports program catalog"
    )
    
    supports_remote_control: bool = Field(
        default=True,
        description="Whether the device supports remote control"
    )
    
    @field_validator('device_id')
    @classmethod
    def validate_device_id(cls, v: str) -> str:
        """Validate device ID format."""
        if not cls.DEVICE_ID_PATTERN.match(v):
            raise ValueError("Device ID must be a 12-digit string")
        return v
    
    @field_validator('host')
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Validate host format."""
        # Simple validation - could be expanded for IP address or hostname validation
        if not v or len(v) < 3:
            raise ValueError("Host must be a valid IP address or hostname")
        return v
    
    def model_dump_json(self, **kwargs) -> str:
        """Export to JSON."""
        return super().model_dump_json(**kwargs)
    
    def model_dump(self, **kwargs) -> dict:
        """Export to dict."""
        return super().model_dump(**kwargs) 