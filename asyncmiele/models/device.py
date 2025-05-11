"""
Models for Miele device information.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from asyncmiele.models.response import MieleResponse


class DeviceIdentification(BaseModel):
    """Model for device identification information."""
    
    device_name: str = Field(default="")
    device_type: str = Field(default="")
    fab_number: str = Field(default="")
    tech_type: str = Field(default="")
    
    @classmethod
    def from_response(cls, response: MieleResponse) -> "DeviceIdentification":
        """
        Create a DeviceIdentification from a MieleResponse.
        
        Args:
            response: The API response containing identification data
            
        Returns:
            A DeviceIdentification instance
        """
        data = response.to_dict()
        return cls(
            device_name=data.get("DeviceName", ""),
            device_type=data.get("Type", {}).get("value_localized", ""),
            fab_number=data.get("DeviceIdentLabel", {}).get("FabNumber", ""),
            tech_type=data.get("DeviceIdentLabel", {}).get("TechType", "")
        )


class DeviceState(BaseModel):
    """Model for device state information."""
    
    status: Optional[str] = None
    program_id: Optional[int] = None
    program_type: Optional[str] = None
    program_phase: Optional[str] = None
    remaining_time: Optional[int] = None
    start_time: Optional[int] = None
    elapsed_time: Optional[int] = None
    
    # Store the raw state data for access to device-specific fields
    raw_state: Dict[str, Any] = Field(default_factory=dict)
    
    @classmethod
    def from_response(cls, response: MieleResponse) -> "DeviceState":
        """
        Create a DeviceState from a MieleResponse.
        
        Args:
            response: The API response containing state data
            
        Returns:
            A DeviceState instance
        """
        data = response.to_dict()
        return cls(
            status=data.get("status", {}).get("value_localized"),
            program_id=data.get("ProgramID"),
            program_type=data.get("programType", {}).get("value_localized"),
            program_phase=data.get("programPhase", {}).get("value_localized"),
            remaining_time=data.get("remainingTime"),
            start_time=data.get("startTime"),
            elapsed_time=data.get("elapsedTime"),
            raw_state=data
        )


class MieleDevice(BaseModel):
    """Model for a Miele device with identification and state."""
    
    id: str = Field(...)
    ident: DeviceIdentification = Field(default_factory=DeviceIdentification)
    state: DeviceState = Field(default_factory=DeviceState)
    
    @property
    def name(self) -> str:
        """Get the device name or tech type if name is not available."""
        if self.ident.device_name:
            return self.ident.device_name
        return self.ident.tech_type 