from dataclasses import dataclass
from typing import List


@dataclass
class DeviceCombinedState:
    appliance_state: int
    operation_state: int
    process_state: int


@dataclass
class SFValue:
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

    hours_of_operation: int | None = None  #: Total operating hours
    cycles_completed: int | None = None  #: Total finished cycles
    energy_wh_total: int | None = None  #: Lifetime energy in *watt-hours*
    water_l_total: int | None = None  #: Lifetime fresh-water usage in litres

    # ------------------------------------------------------------------
    # Convenience helpers

    def energy_kwh(self) -> float | None:
        """Return lifetime energy in kWh (if available)."""
        return (self.energy_wh_total / 1000) if self.energy_wh_total is not None else None

    def estimate_total_cost(self, tariff: TariffConfig) -> float | None:
        """Return monetary cost using *tariff* prices (None if both counters missing)."""
        energy = self.energy_kwh() or 0.0
        water = self.water_l_total or 0.0
        if energy == 0.0 and water == 0.0:
            return None
        return tariff.cost(energy_kwh=energy, water_litres=water) 