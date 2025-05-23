from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Union


class DeviceGenerationType(Enum):
    """Represents different generations of Miele device DOP2 implementations."""
    
    LEGACY = auto()  # Also called dop1 in some contexts
    DOP2 = auto()    # Standard DOP2 implementation
    SEMIPRO = auto() # Semi-professional devices


@dataclass
class DeviceCombinedState:
    """Combined state information from leaf 2/256."""
    
    appliance_state: int
    operation_state: int
    process_state: int


@dataclass
class SFValue:
    """Setting value structure from leaf 2/105.
    
    Represents a device setting with its current value, range, and default.
    """
    
    sf_id: int
    current_value: int
    minimum: int
    maximum: int
    default: int

    @property
    def range(self):
        return self.minimum, self.maximum


@dataclass
class TariffConfig:
    """User-supplied tariff configuration for cost estimation."""

    energy_price_per_kwh: float = 0.30  # Euro or other currency per kWh
    water_price_per_litre: float = 0.003  # Euro per litre

    def cost(self, *, energy_kwh: float = 0.0, water_litres: float = 0.0) -> float:
        """Return monetary cost for given energy ◂kilowatt-hours▸ and water in litres."""
        return (energy_kwh * self.energy_price_per_kwh) + (water_litres * self.water_price_per_litre)


@dataclass
class ConsumptionStats:
    """Aggregated consumption / statistics values read from DOP2 leaves.

    Not every appliance supports every counter, so most fields are optional.
    All values are *cumulative* over lifetime, **not** per-cycle.
    """

    hours_of_operation: Optional[int] = None  #: Total operating hours
    cycles_completed: Optional[int] = None  #: Total finished cycles
    energy_wh_total: Optional[int] = None  #: Lifetime energy in *watt-hours*
    water_l_total: Optional[int] = None  #: Lifetime fresh-water usage in litres

    # ------------------------------------------------------------------
    # Convenience helpers

    def energy_kwh(self) -> Optional[float]:
        """Return lifetime energy in kWh (if available)."""
        return (self.energy_wh_total / 1000) if self.energy_wh_total is not None else None

    def estimate_total_cost(self, tariff: TariffConfig) -> Optional[float]:
        """Return monetary cost using *tariff* prices (None if both counters missing)."""
        energy = self.energy_kwh() or 0.0
        water = self.water_l_total or 0.0
        if energy == 0.0 and water == 0.0:
            return None
        return tariff.cost(energy_kwh=energy, water_litres=water)


# New models based on MieleRESTServer's DOP2 structures

@dataclass
class DeviceIdent:
    """Device identification information from DOP2 leaf."""
    
    device_id: str
    serial_number: Optional[str] = None
    model_name: Optional[str] = None
    tech_type: Optional[str] = None
    manufacturer: Optional[str] = None
    device_type: Optional[int] = None


@dataclass
class DateTime:
    """Date and time information from DOP2 leaf."""
    
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    
    def as_string(self) -> str:
        """Return formatted date and time string."""
        return f"{self.year:04d}-{self.month:02d}-{self.day:02d} {self.hour:02d}:{self.minute:02d}:{self.second:02d}"


@dataclass
class DeviceContext:
    """Device context information from DOP2 leaf."""
    
    context_id: int
    parameters: Dict[int, Any] = field(default_factory=dict)


@dataclass
class ProgramSelection:
    """Program selection data from DOP2 leaf."""
    
    program_id: int
    options: Dict[int, int] = field(default_factory=dict)


@dataclass
class ProgramListEntry:
    """Single program entry from DOP2 program list."""
    
    program_id: int
    name_id: int
    option_group: int
    name: Optional[str] = None


@dataclass
class ProgramList:
    """Program list from DOP2 leaf."""
    
    programs: List[ProgramListEntry] = field(default_factory=list)


@dataclass
class OptionListEntry:
    """Single option entry from DOP2 option list."""
    
    option_id: int
    name_id: int
    default: int
    name: Optional[str] = None
    allowed_values: List[int] = field(default_factory=list)


@dataclass
class OptionList:
    """Option list for a specific program from DOP2 leaf."""
    
    program_id: int
    options: List[OptionListEntry] = field(default_factory=list)


@dataclass
class DeviceState:
    """Device state information from DOP2 leaf."""
    
    state_id: int
    state_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessData:
    """Process data information from DOP2 leaf."""
    
    energy_wh: int = 0
    water_l: int = 0
    duration_s: int = 0
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SFList:
    """List of available settings from DOP2 leaf."""
    
    settings: List[int] = field(default_factory=list)


@dataclass
class NotificationShow:
    """Notification information from DOP2 leaf."""
    
    notification_id: int
    notification_type: int
    notification_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HoursOfOperation:
    """Hours of operation counter from DOP2 leaf."""
    
    total_hours: int


@dataclass
class CycleCounter:
    """Cycle counter from DOP2 leaf."""
    
    total_cycles: int


@dataclass
class SoftwareIds:
    """Software identification information from DOP2 leaf."""
    
    version: str
    build: Optional[str] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NetworkConfig:
    """Network configuration from DOP2 leaf."""
    
    mac_address: Optional[str] = None
    ip_address: Optional[str] = None
    subnet_mask: Optional[str] = None
    gateway: Optional[str] = None
    dns_server: Optional[str] = None
    dhcp_enabled: bool = True


@dataclass
class DOP2Node:
    """Represents a node in the DOP2 tree structure."""
    
    unit: int
    leaves: Dict[int, Any] = field(default_factory=dict)


@dataclass
class DOP2Tree:
    """Complete DOP2 tree structure for a device."""
    
    device_id: str
    generation: DeviceGenerationType = DeviceGenerationType.DOP2
    nodes: Dict[int, DOP2Node] = field(default_factory=dict) 