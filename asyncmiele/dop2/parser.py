"""DOP2 leaf parser.

This module provides parsing functions for DOP2 leaf data structures.
It supports parsing of various DOP2 leaves based on their unit and attribute.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, cast, Union

from .binary import (
    read_u8, read_u16, read_u32, read_s8, read_s16, read_s32,
    read_float, read_string, read_bytes
)
from .models import (
    DeviceCombinedState, SFValue, ConsumptionStats, DeviceIdent,
    DateTime, DeviceContext, ProgramSelection, ProgramList, ProgramListEntry,
    OptionList, OptionListEntry, DeviceState, ProcessData, SFList,
    NotificationShow, HoursOfOperation, CycleCounter, SoftwareIds,
    NetworkConfig, DeviceGenerationType
)

logger = logging.getLogger(__name__)

# Type variable for parser registration
T = TypeVar('T')

# Registry of parser functions for specific leaf types
_LEAF_PARSERS: Dict[Tuple[int, int], Tuple[Type[Any], callable]] = {}


def register_parser(unit: int, attribute: int, model_type: Type[T]) -> callable:
    """Decorator to register a parser function for a specific leaf type.
    
    Args:
        unit: DOP2 unit number
        attribute: DOP2 attribute number
        model_type: The type that the parser function returns
        
    Returns:
        Decorator function
    """
    def decorator(func: callable) -> callable:
        _LEAF_PARSERS[(unit, attribute)] = (model_type, func)
        return func
    return decorator


def detect_device_generation(payload: bytes) -> DeviceGenerationType:
    """Attempt to detect the device generation type based on payload patterns.
    
    This is a heuristic approach that may need refinement as more devices are tested.
    
    Args:
        payload: Raw payload from any DOP2 leaf
        
    Returns:
        Detected device generation type
    """
    # This is a placeholder implementation
    # In a real implementation, we would look for specific patterns
    # that indicate which generation the device belongs to
    
    # For now, default to standard DOP2
    return DeviceGenerationType.DOP2


def parse_leaf(unit: int, attribute: int, payload: bytes) -> Union[DeviceCombinedState, SFValue, HoursOfOperation, CycleCounter, ProcessData, ProgramList, OptionList, SFList, DateTime, Dict[int, str], bytes]:
    """Parse a DOP2 leaf based on its unit and attribute.
    
    This function dispatches to the appropriate parser based on the unit/attribute
    combination. If no specific parser is registered, the raw payload is returned.
    
    Args:
        unit: DOP2 unit number
        attribute: DOP2 attribute number
        payload: Raw binary payload from the leaf
        
    Returns:
        Parsed representation of the leaf data (type depends on the specific leaf)
        
    Raises:
        ValueError: If the payload is invalid for the expected structure
    """
    parser_info = _LEAF_PARSERS.get((unit, attribute))
    
    if parser_info:
        model_type, parser_func = parser_info
        try:
            return parser_func(payload)
        except Exception as e:
            logger.warning(f"Error parsing DOP2 leaf {unit}/{attribute}: {e}")
            # Fall through to return raw payload
    
    # Return raw payload if no parser found or parsing failed
    return payload


# ---------------------------------------------------------------------------
# Parser functions for specific leaf types
# ---------------------------------------------------------------------------

@register_parser(2, 1586, DeviceCombinedState)
def _parse_device_combined_state(payload: bytes) -> DeviceCombinedState:
    """Parse DeviceCombinedState from leaf 2/1586 (corrected from 2/256)."""
    if len(payload) < 6:
        raise ValueError("Payload too short for DeviceCombinedState")
    
    a_state = read_u16(payload, 0)
    o_state = read_u16(payload, 2)
    p_state = read_u16(payload, 4)
    
    return DeviceCombinedState(a_state, o_state, p_state)


# Keep the old parser for backwards compatibility, but log a warning
@register_parser(2, 256, DeviceCombinedState)
def _parse_device_combined_state_legacy(payload: bytes) -> DeviceCombinedState:
    """Parse DeviceCombinedState from legacy leaf 2/256 (deprecated)."""
    logger.warning("Using deprecated leaf 2/256 for DeviceCombinedState. Modern devices use 2/1586.")
    return _parse_device_combined_state(payload)


@register_parser(2, 1585, dict)
def _parse_device_context(payload: bytes) -> dict:
    """Parse DeviceContext from leaf 2/1585."""
    # This is a complex structure that may contain nested data
    # For now, return a basic parsing attempt
    try:
        # Try JSON parsing first (newer devices)
        import json
        return json.loads(payload.decode('utf-8'))
    except:
        # Fall back to raw payload for binary format
        return {"raw_data": payload.hex()}


@register_parser(2, 1577, dict)
def _parse_ps_select(payload: bytes) -> dict:
    """Parse Program Selection from leaf 2/1577."""
    if len(payload) < 8:
        return {"raw_data": payload.hex()}
    
    program_id = read_u32(payload, 0)
    selection_param = read_u32(payload, 4)
    
    return {
        "program_id": program_id,
        "selection_parameter": selection_param
    }


@register_parser(2, 1583, dict)
def _parse_user_request(payload: bytes) -> dict:
    """Parse User Request from leaf 2/1583."""
    if len(payload) < 12:
        return {"raw_data": payload.hex()}
    
    user_request_id = read_u32(payload, 0)
    parameter0 = read_u32(payload, 4)
    parameter1 = read_u32(payload, 8)
    
    return {
        "user_request_id": user_request_id,
        "parameter0": parameter0,
        "parameter1": parameter1
    }


@register_parser(2, 131, dict)
def _parse_notification_show(payload: bytes) -> dict:
    """Parse Notification Show from leaf 2/131."""
    # This structure varies significantly, return basic parsing
    return {"raw_data": payload.hex()}


@register_parser(1, 17, dict)
def _parse_software_ids(payload: bytes) -> dict:
    """Parse Software IDs from leaf 1/17."""
    if len(payload) < 4:
        return {"raw_data": payload.hex()}
    
    num_valid_ids = read_u32(payload, 0)
    return {
        "number_valid_software_ids": num_valid_ids,
        "raw_data": payload.hex()
    }


@register_parser(2, 105, SFValue)
def _parse_sf_value(payload: bytes) -> SFValue:
    """Parse SFValue from leaf 2/105."""
    if len(payload) < 10:
        raise ValueError("Payload too short for SF_Value")
    
    sf_id = read_u16(payload, 0)
    current = read_u16(payload, 2)
    minimum = read_u16(payload, 4)
    maximum = read_u16(payload, 6)
    default = read_u16(payload, 8)
    
    return SFValue(sf_id, current, minimum, maximum, default)


@register_parser(2, 119, HoursOfOperation)
def _parse_hours_of_operation(payload: bytes) -> HoursOfOperation:
    """Parse HoursOfOperation from leaf 2/119."""
    if len(payload) < 4:
        raise ValueError("Payload too short for HoursOfOperation")
    
    hours = read_u32(payload, 0)
    return HoursOfOperation(hours)


@register_parser(2, 138, CycleCounter)
def _parse_cycle_counter(payload: bytes) -> CycleCounter:
    """Parse CycleCounter from leaf 2/138."""
    if len(payload) < 4:
        raise ValueError("Payload too short for CycleCounter")
    
    cycles = read_u32(payload, 0)
    return CycleCounter(cycles)


@register_parser(2, 6195, ProcessData)
def _parse_process_data(payload: bytes) -> ProcessData:
    """Parse ProcessData from leaf 2/6195."""
    if len(payload) < 8:
        raise ValueError("Payload too short for ProcessData")
    
    energy_wh = read_u32(payload, 0)
    water_l = read_u32(payload, 4)
    
    # Create additional data dictionary for any extra fields
    additional_data = {}
    if len(payload) >= 12:
        duration_s = read_u32(payload, 8)
        return ProcessData(energy_wh, water_l, duration_s, additional_data)
    
    return ProcessData(energy_wh, water_l, 0, additional_data)


@register_parser(2, 1584, ProgramList)
def _parse_program_list(payload: bytes) -> ProgramList:
    """Parse ProgramList from leaf 2/1584."""
    # This is a JSON-based leaf in newer firmware
    # We'll handle it as a special case by returning a structured object
    
    # First try to parse as JSON
    try:
        import json
        data = json.loads(payload)
        
        program_list = ProgramList()
        if "programIds" in data and isinstance(data["programIds"], list):
            for pid in data["programIds"]:
                program = ProgramListEntry(
                    program_id=pid,
                    name_id=0,  # Not available in this format
                    option_group=0  # Not available in this format
                )
                program_list.programs.append(program)
        
        return program_list
    except Exception:
        # If JSON parsing fails, try binary format
        pass
    
    # Binary format fallback - 12 bytes per entry
    entry_size = 12
    if len(payload) % entry_size:
        raise ValueError(f"Program list length {len(payload)} not a multiple of {entry_size}")
    
    program_list = ProgramList()
    for offset in range(0, len(payload), entry_size):
        pid = read_u16(payload, offset)
        name_id = read_u16(payload, offset + 2)
        opt_grp = read_u16(payload, offset + 4)
        
        program = ProgramListEntry(
            program_id=pid,
            name_id=name_id,
            option_group=opt_grp
        )
        program_list.programs.append(program)
    
    return program_list


@register_parser(14, 1570, ProgramList)
def _parse_program_list_legacy(payload: bytes) -> ProgramList:
    """Parse legacy ProgramList from leaf 14/1570."""
    # Binary format - 12 bytes per entry
    entry_size = 12
    if len(payload) % entry_size:
        raise ValueError(f"Program list length {len(payload)} not a multiple of {entry_size}")
    
    program_list = ProgramList()
    for offset in range(0, len(payload), entry_size):
        pid = read_u16(payload, offset)
        name_id = read_u16(payload, offset + 2)
        opt_grp = read_u16(payload, offset + 4)
        
        program = ProgramListEntry(
            program_id=pid,
            name_id=name_id,
            option_group=opt_grp
        )
        program_list.programs.append(program)
    
    return program_list


@register_parser(14, 1571, OptionList)
def _parse_option_list(payload: bytes) -> OptionList:
    """Parse OptionList from leaf 14/1571."""
    # Binary format - 8 bytes per entry
    entry_size = 8
    if len(payload) % entry_size:
        raise ValueError(f"Option list length {len(payload)} not a multiple of {entry_size}")
    
    # The program ID should be provided as idx1 parameter
    # For now, we'll use 0 as a default
    program_id = 0
    
    option_list = OptionList(program_id=program_id)
    for offset in range(0, len(payload), entry_size):
        oid = read_u16(payload, offset)
        name_id = read_u16(payload, offset + 2)
        default = read_u16(payload, offset + 4)
        
        option = OptionListEntry(
            option_id=oid,
            name_id=name_id,
            default=default
        )
        option_list.options.append(option)
    
    return option_list


@register_parser(14, 2570, dict)
def _parse_string_table(payload: bytes) -> Dict[int, str]:
    """Parse string table from leaf 14/2570."""
    parts = payload.split(b"\x00")
    # Last entry after final NUL is empty – drop it
    strings = [s.decode("utf-8", errors="replace") for s in parts if s]
    return {idx: text for idx, text in enumerate(strings)}


@register_parser(2, 293, DateTime)
def _parse_date_time(payload: bytes) -> DateTime:
    """Parse DateTime from leaf 2/293."""
    if len(payload) < 7:
        raise ValueError("Payload too short for DateTime")
    
    year = read_u16(payload, 0)
    month = read_u8(payload, 2)
    day = read_u8(payload, 3)
    hour = read_u8(payload, 4)
    minute = read_u8(payload, 5)
    second = read_u8(payload, 6)
    
    return DateTime(year, month, day, hour, minute, second)


@register_parser(2, 286, SFList)
def _parse_sf_list(payload: bytes) -> SFList:
    """Parse SFList from leaf 2/286."""
    # Each setting ID is a 16-bit integer
    if len(payload) % 2:
        raise ValueError("SF list length not a multiple of 2")
    
    sf_list = SFList()
    for offset in range(0, len(payload), 2):
        sf_id = read_u16(payload, offset)
        sf_list.settings.append(sf_id)
    
    return sf_list 