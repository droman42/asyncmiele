"""Program-related DOP2 functionality.

This module provides functions for parsing and building program-related DOP2 structures.
It consolidates functionality previously spread across multiple modules.
"""

from typing import Dict, List, Any, Mapping, Optional

from .binary import read_u16, write_u16, pad_to_block_size
from .models import ProgramList, ProgramListEntry, OptionList, OptionListEntry


def parse_program_list(payload: bytes) -> List[Dict[str, Any]]:
    """Parse program list data from leaf 14/1570.
    
    Args:
        payload: Raw binary payload from the leaf
        
    Returns:
        List of program dictionaries
        
    Raises:
        ValueError: If the payload has an invalid format
    """
    # Binary format - 12 bytes per entry
    entry_size = 12
    if len(payload) % entry_size:
        raise ValueError(f"Program list length {len(payload)} not a multiple of {entry_size}")
    
    programs: List[Dict[str, Any]] = []
    for offset in range(0, len(payload), entry_size):
        pid = read_u16(payload, offset)
        str_id = read_u16(payload, offset + 2)
        opt_grp = read_u16(payload, offset + 4)
        programs.append({
            "id": pid,
            "name_id": str_id,
            "option_group": opt_grp,
            "options": [],  # filled later
        })
    return programs


def parse_option_list(payload: bytes) -> List[Dict[str, Any]]:
    """Parse option list data from leaf 14/1571.
    
    Args:
        payload: Raw binary payload from the leaf
        
    Returns:
        List of option dictionaries
        
    Raises:
        ValueError: If the payload has an invalid format
    """
    # Binary format - 8 bytes per entry
    entry_size = 8
    if len(payload) % entry_size:
        raise ValueError(f"Option list length {len(payload)} not a multiple of {entry_size}")
    
    items: List[Dict[str, Any]] = []
    for offset in range(0, len(payload), entry_size):
        oid = read_u16(payload, offset)
        str_id = read_u16(payload, offset + 2)
        default = read_u16(payload, offset + 4)
        items.append({
            "id": oid,
            "name_id": str_id,
            "default": default,
        })
    return items


def build_string_map(blob: bytes) -> Mapping[int, str]:
    """Build a mapping of string IDs to UTF-8 strings from leaf 14/2570.
    
    Args:
        blob: Raw binary payload from the leaf
        
    Returns:
        Dictionary mapping string IDs to strings
    """
    parts = blob.split(b"\x00")
    # Last entry after final NUL is empty – drop it
    strings = [s.decode("utf-8", errors="replace") for s in parts if s]
    return {idx: text for idx, text in enumerate(strings)}


def parse_program_list_from_leaf_2_1584(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse program list from leaf 2/1584 result.
    
    Args:
        data: Parsed JSON data from leaf 2/1584
        
    Returns:
        List of program dictionaries
    """
    programs = []
    if "programIds" in data and isinstance(data["programIds"], list):
        for pid in data["programIds"]:
            programs.append({
                "id": pid,
                "name": f"Program_{pid}",  # Default name
                "options": []  # Will be filled in later
            })
    return programs


def build_program_selection(program_id: int, options: Optional[Mapping[int, int]] = None) -> bytes:
    """Build a program selection payload for DOP2.
    
    Args:
        program_id: ID of the program to select
        options: Dictionary mapping option IDs to values
        
    Returns:
        Binary payload for DOP2 write
    """
    options = options or {}
    payload = bytearray()
    
    # Program ID (2 bytes)
    payload += write_u16(program_id)
    
    # Options (4 bytes each: 2 for ID, 2 for value)
    for opt_id, value in options.items():
        payload += write_u16(opt_id)
        payload += write_u16(value)
    
    # Pad to 16-byte boundary for AES encryption
    return pad_to_block_size(bytes(payload)) 