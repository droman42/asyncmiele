"""
Network configuration models for Miele device WiFi setup.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class SecurityType(str, Enum):
    """WiFi security types supported by Miele devices."""
    NONE = "None"
    WEP = "WEP"
    WPA_PSK = "WPA-PSK"
    WPA2 = "WPA2"
    WPA2_PSK = "WPA2-PSK"
    WPA_WPA2_PSK = "WPA/WPA2-PSK"


class MieleNetworkConfig(BaseModel):
    """
    Network configuration for setting up a Miele device's WiFi connection.
    
    This model is used to configure the WiFi settings on a Miele device
    during the initial setup process.
    """
    # WiFi network SSID
    ssid: str = Field(
        description="WiFi network SSID"
    )
    
    # WiFi security type
    security_type: SecurityType = Field(
        alias="Sec",
        default=SecurityType.WPA2,
        description="WiFi security type"
    )
    
    # WiFi password
    password: Optional[str] = Field(
        alias="Key",
        default=None,
        description="WiFi network password"
    )
    
    # Hidden network flag
    hidden: bool = Field(
        default=False,
        description="Whether the WiFi network is hidden"
    )
    
    @field_validator('ssid')
    @classmethod
    def validate_ssid(cls, v: str) -> str:
        """Validate SSID."""
        if not v:
            raise ValueError("SSID cannot be empty")
        if len(v) > 32:
            raise ValueError("SSID must be 32 characters or less")
        return v
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: Optional[str], info) -> Optional[str]:
        """Validate password based on security type."""
        security_type = info.data.get('security_type', SecurityType.WPA2)
        
        # Password not needed for open networks
        if security_type == SecurityType.NONE:
            return None
            
        # Password required for secured networks
        if not v:
            raise ValueError(f"Password is required for {security_type} networks")
            
        # WPA2 password length validation
        if security_type in [SecurityType.WPA2, SecurityType.WPA2_PSK, SecurityType.WPA_WPA2_PSK]:
            if len(v) < 8 or len(v) > 63:
                raise ValueError("WPA2 password must be between 8 and 63 characters")
                
        return v
    
    class Config:
        """Pydantic configuration."""
        populate_by_name = True  # Allow both alias and field name for initialization
    
    def model_dump_json(self, **kwargs) -> str:
        """Export to JSON using the format expected by Miele devices."""
        kwargs.setdefault("by_alias", True)
        return super().model_dump_json(**kwargs)
    
    def model_dump(self, **kwargs) -> dict:
        """Export to dict using the format expected by Miele devices."""
        kwargs.setdefault("by_alias", True)
        return super().model_dump(**kwargs) 