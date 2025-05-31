"""
Device profile model to track device capabilities and configuration preferences.
"""

from typing import Dict, Any, Optional, Set
from datetime import datetime
from pydantic import BaseModel, Field

from asyncmiele.capabilities import DeviceCapability
from asyncmiele.enums import DeviceTypeMiele
from asyncmiele.models.credentials import MieleCredentials
from asyncmiele.programs.catalog import ProgramCatalog


class DeviceProfile(BaseModel):
    """
    Enhanced device profile that includes configuration, capabilities, and preferences.
    
    This model is used to track comprehensive information about a device, including
    its connection configuration, detected capabilities, program catalog, and user preferences.
    This is the primary configuration model for the configuration-driven service architecture.
    """
    
    # Core device information
    device_id: str = Field(..., description="Unique device identifier")
    device_type: DeviceTypeMiele = Field(DeviceTypeMiele.NoUse, description="Type of device")
    friendly_name: Optional[str] = Field(None, description="User-friendly name")
    
    # Connection information (direct fields - no config wrapper)
    host: str = Field(..., description="IP address or hostname of the device")
    timeout: float = Field(default=5.0, description="Default timeout for operations in seconds")
    
    # Security credentials
    credentials: MieleCredentials = Field(..., description="Security credentials")
    
    # Capabilities (as sets for consistency)
    capabilities: Set[DeviceCapability] = Field(
        default_factory=set,
        description="Detected device capabilities"
    )
    failed_capabilities: Set[DeviceCapability] = Field(
        default_factory=set,
        description="Capabilities that were tested and failed"
    )
    capability_detection_date: Optional[datetime] = Field(
        default=None,
        description="When capabilities were last detected"
    )
    
    # Program catalog
    program_catalog: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Complete program catalog for the device"
    )
    program_catalog_extraction_method: Optional[str] = Field(
        default=None, 
        description="Method used to extract catalog (dop2_new, dop2_legacy, etc.)"
    )
    
    # Preferences 
    wake_before_commands: bool = Field(
        default=True, 
        description="Whether to wake device before sending commands"
    )
    auto_detect_capabilities: bool = Field(
        default=True,
        description="Whether to automatically detect device capabilities"
    )
    
    class Config:
        """Pydantic model configuration."""
        # Allow arbitrary types for DeviceCapability enum
        arbitrary_types_allowed = True
        # Allow datetime objects for JSON serialization
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    # Capability management methods
    def has_capability(self, capability: DeviceCapability) -> bool:
        """Check if device has a specific capability."""
        return capability in self.capabilities
    
    def has_any_capability(self, *capabilities: DeviceCapability) -> bool:
        """Check if device has any of the specified capabilities."""
        return bool(self.capabilities.intersection(capabilities))
    
    def has_all_capabilities(self, *capabilities: DeviceCapability) -> bool:
        """Check if device has all of the specified capabilities."""
        return set(capabilities).issubset(self.capabilities)
    
    def mark_capability(self, capability: DeviceCapability, success: bool) -> None:
        """Mark a capability as tested, updating both capabilities and failed_capabilities."""
        if success:
            self.capabilities.add(capability)
            self.failed_capabilities.discard(capability)
        else:
            self.failed_capabilities.add(capability)
            self.capabilities.discard(capability)
    
    def get_missing_capabilities(self, required: Set[DeviceCapability]) -> Set[DeviceCapability]:
        """Get capabilities that are required but not supported."""
        return required - self.capabilities
    
    def get_supported_features(self) -> Set[DeviceCapability]:
        """Get all supported capabilities."""
        return self.capabilities.copy()
    
    # JSON serialization helpers for grouped capabilities
    def model_dump_json_friendly(self) -> Dict[str, Any]:
        """Export with grouped capabilities and flat structure for JSON files."""
        data = self.model_dump(exclude={'capabilities', 'failed_capabilities', 'capability_detection_date'})
        
        # Fix device_type serialization - convert enum to name string
        if 'device_type' in data:
            data['device_type'] = self.device_type.name
        
        # Group capabilities
        data['capabilities'] = {
            'supported': [cap.name for cap in self.capabilities],
            'failed': [cap.name for cap in self.failed_capabilities],
            'detection_date': self.capability_detection_date.isoformat() if self.capability_detection_date else None
        }
        
        return data
    
    @classmethod
    def from_json_friendly(cls, data: Dict[str, Any]) -> 'DeviceProfile':
        """Create from JSON with grouped capabilities converted to enum sets."""
        # Handle device_type conversion from name string to enum
        if 'device_type' in data and isinstance(data['device_type'], str):
            device_type_name = data['device_type']
            if hasattr(DeviceTypeMiele, device_type_name):
                data['device_type'] = getattr(DeviceTypeMiele, device_type_name)
            else:
                # Fallback to NoUse if enum name not found
                data['device_type'] = DeviceTypeMiele.NoUse
        
        # Handle grouped capabilities structure
        if 'capabilities' in data and isinstance(data['capabilities'], dict):
            caps_data = data.pop('capabilities')
            
            # Extract supported capabilities
            supported = set()
            if 'supported' in caps_data:
                for cap_name in caps_data['supported']:
                    if hasattr(DeviceCapability, cap_name):
                        supported.add(getattr(DeviceCapability, cap_name))
            data['capabilities'] = supported
            
            # Extract failed capabilities  
            failed = set()
            if 'failed' in caps_data:
                for cap_name in caps_data['failed']:
                    if hasattr(DeviceCapability, cap_name):
                        failed.add(getattr(DeviceCapability, cap_name))
            data['failed_capabilities'] = failed
            
            # Extract detection date
            if 'detection_date' in caps_data and caps_data['detection_date']:
                data['capability_detection_date'] = datetime.fromisoformat(caps_data['detection_date'])
        
        return cls(**data)
    
    # Legacy compatibility properties for current usage patterns
    @property
    def capabilities_list(self) -> list[str]:
        """Get capabilities as a list of names for JSON serialization."""
        return [cap.name for cap in self.capabilities]
    
    @property
    def failed_capabilities_list(self) -> list[str]:
        """Get failed capabilities as a list of names for JSON serialization."""
        return [cap.name for cap in self.failed_capabilities]
    
    # Cache management (for backward compatibility)
    def cache_value(self, key: str, value: Any) -> None:
        """Cache a value for the device (deprecated - use external caching)."""
        # This method is kept for backward compatibility but does nothing
        # External caching should be used instead
        pass
    
    def get_cached_value(self, key: str, default: Any = None) -> Any:
        """Get a cached value for the device (deprecated - use external caching)."""
        # This method is kept for backward compatibility but returns default
        # External caching should be used instead
        return default
    
    def clear_cache(self) -> None:
        """Clear all cached information for the device (deprecated - use external caching)."""
        # This method is kept for backward compatibility but does nothing
        # External caching should be used instead
        pass
    
    # Program catalog management methods
    def save_program_catalog(self, catalog: "ProgramCatalog") -> None:
        """Save a program catalog to this device profile.
        
        Args:
            catalog: Program catalog to save
        """
        self.program_catalog = catalog.to_dict()
        self.program_catalog_extraction_method = catalog.extraction_method

    @classmethod
    def load_program_catalog(cls, profile: "DeviceProfile") -> Optional["ProgramCatalog"]:
        """Load a program catalog from a device profile.
        
        Args:
            profile: Device profile to load from
            
        Returns:
            Program catalog if available, None otherwise
        """
        if not profile.program_catalog:
            return None
            
        return ProgramCatalog.from_dict(
            profile.program_catalog,
            extraction_method=profile.program_catalog_extraction_method
        )
    
    def has_program_catalog(self) -> bool:
        """Check if this profile has a valid program catalog.
        
        Returns:
            True if a program catalog is available and valid
        """
        return (self.program_catalog is not None and 
                isinstance(self.program_catalog, dict) and
                len(self.program_catalog.get("programs", [])) > 0)
    
    def save_program_catalog_data(self, catalog_data: Dict[str, Any], extraction_method: str = "unknown") -> None:
        """Save program catalog from dictionary data.
        
        Args:
            catalog_data: Dictionary containing catalog data
            extraction_method: Method used to extract the catalog
        """
        if not isinstance(catalog_data, dict):
            raise TypeError("catalog_data must be a dictionary")
        
        self.program_catalog = catalog_data
        self.program_catalog_extraction_method = extraction_method
    
    def get_program_catalog_data(self) -> Optional[Dict[str, Any]]:
        """Get program catalog as dictionary data.
        
        Returns:
            Dictionary containing catalog data or None if not available
        """
        return self.program_catalog 