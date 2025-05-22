"""
Device profile model to track device capabilities and configuration preferences.
"""

from typing import Dict, Any, Optional, Set
from pydantic import BaseModel, Field

from asyncmiele.capabilities import DeviceCapability
from asyncmiele.enums import DeviceType
from asyncmiele.models.credentials import MieleCredentials
from asyncmiele.models.device_config import MieleDeviceConfig


class DeviceProfile(BaseModel):
    """
    Device profile that includes configuration, capabilities, and preferences.
    
    This model is used to track information about a device, including its
    configuration, detected capabilities, and user preferences.
    """
    
    # Basic device identification
    device_id: str = Field(..., description="Unique device identifier")
    device_type: DeviceType = Field(DeviceType.NoUse, description="Type of device")
    friendly_name: Optional[str] = Field(None, description="User-friendly name for the device")
    
    # Connection configuration
    config: MieleDeviceConfig = Field(..., description="Device connection configuration")
    credentials: MieleCredentials = Field(..., description="Security credentials for the device")
    
    # Capability information
    capabilities: DeviceCapability = Field(
        default=DeviceCapability.NONE, 
        description="Detected device capabilities"
    )
    failed_capabilities: Set[DeviceCapability] = Field(
        default_factory=set,
        description="Capabilities that were tested and failed"
    )
    
    # User preferences
    wake_before_commands: bool = Field(
        default=True, 
        description="Whether to wake the device before sending commands"
    )
    auto_detect_capabilities: bool = Field(
        default=True,
        description="Whether to automatically detect device capabilities"
    )
    timeout: float = Field(
        default=5.0,
        description="Default timeout for operations with this device (seconds)"
    )
    
    # Cached information
    cached_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Cached device information to reduce API calls"
    )
    
    class Config:
        """Pydantic model configuration."""
        # Allow arbitrary types for DeviceCapability enum
        arbitrary_types_allowed = True
    
    @property
    def host(self) -> str:
        """Get the host address for the device."""
        return self.config.host
    
    def has_capability(self, capability: DeviceCapability) -> bool:
        """
        Check if the device has a specific capability.
        
        Args:
            capability: The capability to check
            
        Returns:
            True if the device has the capability, False otherwise
        """
        return bool(self.capabilities & capability)
    
    def mark_capability(self, capability: DeviceCapability, success: bool) -> None:
        """
        Mark a capability as tested, updating both capabilities and failed_capabilities.
        
        Args:
            capability: The capability being tested
            success: Whether the test was successful
        """
        if success:
            # Add the capability
            self.capabilities |= capability
            # Remove from failed capabilities if present
            if capability in self.failed_capabilities:
                self.failed_capabilities.remove(capability)
        else:
            # Add to failed capabilities
            self.failed_capabilities.add(capability)
            # Remove the capability
            self.capabilities &= ~capability
    
    def cache_value(self, key: str, value: Any) -> None:
        """
        Cache a value for the device.
        
        Args:
            key: The key to cache the value under
            value: The value to cache
        """
        self.cached_info[key] = value
    
    def get_cached_value(self, key: str, default: Any = None) -> Any:
        """
        Get a cached value for the device.
        
        Args:
            key: The key to get the cached value for
            default: The default value to return if the key is not cached
            
        Returns:
            The cached value, or the default if not found
        """
        return self.cached_info.get(key, default)
    
    def clear_cache(self) -> None:
        """Clear all cached information for the device."""
        self.cached_info.clear()
    
    @classmethod
    def from_config(
        cls, 
        config: MieleDeviceConfig, 
        credentials: MieleCredentials, 
        device_id: str, 
        device_type: DeviceType = DeviceType.NoUse,
        **kwargs
    ) -> "DeviceProfile":
        """
        Create a device profile from a device configuration.
        
        Args:
            config: The device configuration
            credentials: The security credentials for the device
            device_id: The device identifier
            device_type: The device type
            **kwargs: Additional keyword arguments to pass to the constructor
            
        Returns:
            A new DeviceProfile instance
        """
        return cls(
            device_id=device_id,
            device_type=device_type,
            config=config,
            credentials=credentials,
            **kwargs
        ) 