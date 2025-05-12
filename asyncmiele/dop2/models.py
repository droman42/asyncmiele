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