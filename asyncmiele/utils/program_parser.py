"""Program catalog parsing utilities.

This module provides functions for parsing binary program catalog data
from Miele appliances. These functions are extracted from the dump_program_catalog.py
script for reuse within the library.
"""

import struct
from typing import Mapping, List, Dict, Any

# ---------------------------------------------------------------------------
# Minimal binary decoders for the two DOP2 leaves we need.
# These are deliberately conservative: the format has been observed to be
# stable across appliances but is *not* officially documented.
# ---------------------------------------------------------------------------

# Helpers -------------------------------------------------------------------

U16 = struct.Struct('>H')  # network-byte-order unsigned-16


def _u16(data: bytes, offset: int) -> int:
    """Read one uint16 from *data* starting at *offset*."""
    return U16.unpack_from(data, offset)[0]


# Leaf 14/1570 – Programme list ------------------------------------------------
# Each entry is 12 bytes in firmware captured so far:
#   0–1 : programme-id  (uint16)
#   2–3 : string-id     (uint16)  name in string table 14/2570
#   4–5 : option-group  (uint16)
#   6–11: reserved / flags
_ENTRY_SIZE = 12


def parse_program_list(payload: bytes) -> List[Dict[str, Any]]:
    """Parse program list data from leaf 14/1570."""
    if len(payload) % _ENTRY_SIZE:
        raise ValueError(f"Program list length {len(payload)} not a multiple of {_ENTRY_SIZE}")

    programs: List[Dict[str, Any]] = []
    for ofs in range(0, len(payload), _ENTRY_SIZE):
        pid = _u16(payload, ofs)
        str_id = _u16(payload, ofs + 2)
        opt_grp = _u16(payload, ofs + 4)
        programs.append({
            "id": pid,
            "name_id": str_id,
            "option_group": opt_grp,
            "options": [],  # filled later
        })
    return programs


# Leaf 14/1571 – option list per programme ----------------------------------
# Layout seen so far (8 bytes per entry):
#   0–1 : option-id   (uint16)
#   2–3 : string-id   (uint16)
#   4–5 : default     (uint16)
#   6–7 : reserved / flags
_OPT_SIZE = 8


def parse_option_list(payload: bytes) -> List[Dict[str, Any]]:
    """Parse option list data from leaf 14/1571."""
    if len(payload) % _OPT_SIZE:
        raise ValueError(f"Option list length {len(payload)} not a multiple of {_OPT_SIZE}")
    items: List[Dict[str, Any]] = []
    for ofs in range(0, len(payload), _OPT_SIZE):
        oid = _u16(payload, ofs)
        str_id = _u16(payload, ofs + 2)
        default = _u16(payload, ofs + 4)
        items.append({
            "id": oid,
            "name_id": str_id,
            "default": default,
        })
    return items


# Leaf 14/2570 – string table -------------------------------------------------
# Binary blob of UTF-8 null-terminated strings.  The *string-id* is an index
# into that table, counting only *completed strings* (id 0 = first string).


def build_string_map(blob: bytes) -> Mapping[int, str]:
    """Build a mapping of string IDs to UTF-8 strings from leaf 14/2570."""
    parts = blob.split(b"\x00")
    # Last entry after final NUL is empty – drop it
    strings = [s.decode("utf-8", errors="replace") for s in parts if s]
    return {idx: text for idx, text in enumerate(strings)}


# ---------------------------------------------------------------------------
# Leaf 2/1584 - Program list
# ---------------------------------------------------------------------------

def parse_program_list_from_leaf_2_1584(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse program list from leaf 2/1584 result.
    
    This leaf uses a different format than 14/1570. It contains a programIds array
    that we need to extract into our standard program list format.
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