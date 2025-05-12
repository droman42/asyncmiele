from __future__ import annotations

from typing import Any

from .models import DeviceCombinedState, SFValue


def _u16(b1: int, b2: int) -> int:
    return (b1 << 8) + b2


def parse_leaf(unit: int, attribute: int, payload: bytes) -> Any:
    """Parse a limited subset of DOP2 leaves.

    Currently supports:
        • DeviceCombinedState (2/256): three U16 values
        • SF_Value (2/105): SFID + four U16 values (current, min, max, default)

    For unknown leaves the *raw* payload is returned.
    """
    if (unit, attribute) == (2, 256):
        if len(payload) < 6:
            raise ValueError("Payload too short for DeviceCombinedState")
        a_state = _u16(payload[0], payload[1])
        o_state = _u16(payload[2], payload[3])
        p_state = _u16(payload[4], payload[5])
        return DeviceCombinedState(a_state, o_state, p_state)

    if (unit, attribute) == (2, 105):
        if len(payload) < 10:
            raise ValueError("Payload too short for SF_Value")
        sf_id = _u16(payload[0], payload[1])
        current = _u16(payload[2], payload[3])
        minimum = _u16(payload[4], payload[5])
        maximum = _u16(payload[6], payload[7])
        default = _u16(payload[8], payload[9])
        return SFValue(sf_id, current, minimum, maximum, default)

    # fallback
    return payload 