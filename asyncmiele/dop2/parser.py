from __future__ import annotations

from typing import Any

from .models import DeviceCombinedState, SFValue


def _u16(b1: int, b2: int) -> int:
    return (b1 << 8) + b2


def _u32(b0: int, b1: int, b2: int, b3: int) -> int:
    """Return 32-bit big-endian unsigned integer assembled from 4 bytes."""
    return (b0 << 24) + (b1 << 16) + (b2 << 8) + b3


def parse_leaf(unit: int, attribute: int, payload: bytes) -> Any:
    """Parse a limited subset of DOP2 leaves.

    Currently supports:
        • DeviceCombinedState (2/256): three U16 values
        • SF_Value (2/105): SFID + four U16 values (current, min, max, default)
        • HoursOfOperation (2/119): 32-bit unsigned integer
        • CycleCounter (2/138): 32-bit unsigned integer
        • ProcessData (2/6195): energy and water totals

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

    if (unit, attribute) == (2, 119):
        if len(payload) < 4:
            raise ValueError("Payload too short for HoursOfOperation (expected 4 bytes)")
        return _u32(payload[0], payload[1], payload[2], payload[3])

    if (unit, attribute) == (2, 138):
        if len(payload) < 4:
            raise ValueError("Payload too short for CycleCounter (expected 4 bytes)")
        return _u32(payload[0], payload[1], payload[2], payload[3])

    if (unit, attribute) == (2, 6195):
        # ProcessData struct – indices 16/17 map to lifetime energy and water.
        # For a minimal implementation we assume wire format stores those two
        # counters as consecutive 32-bit big-endian unsigned integers.
        if len(payload) < 8:
            raise ValueError("Payload too short for ProcessData energy/water totals (expected ≥8 bytes)")
        energy_wh = _u32(payload[0], payload[1], payload[2], payload[3])
        water_l = _u32(payload[4], payload[5], payload[6], payload[7])
        return {"energy_wh_total": energy_wh, "water_l_total": water_l}

    # fallback
    return payload 