"""
Models for Miele device information.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from asyncmiele.models.response import MieleResponse
from asyncmiele.enums import Status as StatusEnum, ProgramPhase as ProgramPhaseEnum, ProgramId as ProgramIdEnum


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
    status_code: Optional[int] = None
    status_enum: Optional[StatusEnum] = None
    program_id: Optional[int] = None
    program_type: Optional[str] = None
    program_phase: Optional[str] = None
    program_phase_code: Optional[int] = None
    program_phase_enum: Optional[ProgramPhaseEnum] = None
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
        status_field = data.get("status", {})
        return cls(
            status=status_field.get("value_localized") if isinstance(status_field, dict) else None,
            status_code=status_field.get("value_raw") if isinstance(status_field, dict) else status_field if isinstance(status_field, int) else None,
            status_enum=(
                (lambda v: StatusEnum(v) if v in StatusEnum._value2member_map_ else None)(
                    status_field.get("value_raw") if isinstance(status_field, dict) else status_field
                )
            ),
            program_id=data.get("ProgramID"),
            program_type=data.get("programType", {}).get("value_localized"),
            program_phase=data.get("programPhase", {}).get("value_localized"),
            program_phase_code=data.get("programPhase", {}).get("value_raw"),
            program_phase_enum=(
                (lambda v: ProgramPhaseEnum(v) if v in ProgramPhaseEnum._value2member_map_ else None)(
                    data.get("programPhase", {}).get("value_raw")
                )
            ),
            remaining_time=data.get("remainingTime"),
            start_time=data.get("startTime"),
            elapsed_time=data.get("elapsedTime"),
            raw_state=data
        )

    # ------------------------------------------------------------------
    # Convenience properties (Phase-3)
    # ------------------------------------------------------------------

    @property
    def status_name(self) -> Optional[str]:
        """Human-readable name resolving :pyattr:`status_code`."""
        from asyncmiele.enums import status_name as _status_name  # late import to avoid cycles

        if self.status_code is not None:
            return _status_name(self.status_code)
        return None

    @property
    def program_phase_name(self) -> Optional[str]:
        """Human-readable name for :pyattr:`program_phase_code`."""
        from asyncmiele.enums import ProgramPhase as _Phase

        if self.program_phase_code is not None and self.program_phase_code in _Phase._value2member_map_:
            return _Phase(self.program_phase_code).name
        return None

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