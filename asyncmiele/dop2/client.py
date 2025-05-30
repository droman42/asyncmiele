"""
DOP2 protocol client for Miele devices.

This module provides protocol-level operations for DOP2 without HTTP dependencies.
The actual HTTP communication is handled by MieleClient.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from urllib.parse import quote

from asyncmiele.dop2.binary import write_u16
from asyncmiele.dop2.explorer import DOP2Explorer
from asyncmiele.dop2.generation import detector
from asyncmiele.dop2.models import (
    DeviceGenerationType, ConsumptionStats, HoursOfOperation, 
    CycleCounter, ProcessData, SFValue
)
from asyncmiele.dop2.parser import parse_leaf
from asyncmiele.dop2.programs import build_program_selection, parse_program_list, parse_option_list, build_string_map
from asyncmiele.enums import DeviceType

logger = logging.getLogger(__name__)

class DOP2Client:
    """Pure protocol handler for DOP2 operations.
    
    This class handles DOP2 protocol operations without making HTTP calls.
    All HTTP communication is delegated to MieleClient.
    """
    
    # System leaves (Unit 1)
    LEAF_SYSTEM_INFO = (1, 2)
    LEAF_SYSTEM_STATUS = (1, 3)
    LEAF_SYSTEM_CONFIG = (1, 4)

    # Core DOP2 leaves (Unit 2) - Updated to match MieleRESTServer
    LEAF_COMBINED_STATE = (2, 1586)  # Fixed: was 2/256, now matches MieleRESTServer
    LEAF_SF_VALUE = (2, 105)
    LEAF_PROGRAM_LIST = (2, 1584)
    LEAF_HOURS_OF_OPERATION = (2, 119)
    LEAF_CYCLE_COUNTER = (2, 138)
    LEAF_CONSUMPTION_STATS = (2, 6195)
    LEAF_DEVICE_STATE = (2, 286)
    LEAF_DEVICE_IDENT = (2, 293)
    
    # Additional leaves from MieleRESTServer reference
    LEAF_DEVICE_CONTEXT = (2, 1585)
    LEAF_PS_SELECT = (2, 1577)
    LEAF_PS_CONTEXT = (2, 1574)
    LEAF_USER_REQUEST = (2, 1583)
    LEAF_NOTIFICATION_SHOW = (2, 131)
    LEAF_SF_LIST = (2, 1589)
    LEAF_DATE_TIME = (2, 293)

    # Semi-pro leaves (Unit 3)
    LEAF_SEMIPRO_CONFIG = (3, 1000)

    # Legacy leaves (Unit 14)
    LEAF_LEGACY_PROGRAM_LIST = (14, 1570)
    LEAF_LEGACY_OPTION_LIST = (14, 1571)
    LEAF_LEGACY_STRING_TABLE = (14, 2570)
    
    # System information leaves (Unit 1) - Additional from MieleRESTServer
    LEAF_SOFTWARE_IDS = (1, 17)
    
    # File transfer leaves (Unit 15) - From MieleRESTServer
    LEAF_FT_LAST_UPDATE_INFO = (15, 199)
    LEAF_FT_UPDATE_CONTROL = (15, 170)
    LEAF_FT_FILE_INFO = (15, 1588)
    LEAF_FT_FILE_WRITE = (15, 1590)
    LEAF_FT_PUBLIC_KEY = (15, 287)
    
    def __init__(self):
        """Initialize the DOP2Client as a pure protocol handler."""
        self._cache = {}  # Optional cache for leaf metadata

    def build_leaf_path(self, device_id: str, unit: int, attribute: int, 
                       idx1: int = 0, idx2: int = 0) -> str:
        """Build the resource path for a DOP2 leaf.
        
        Args:
            device_id: Device identifier
            unit: DOP2 unit number
            attribute: DOP2 attribute number
            idx1: First index parameter
            idx2: Second index parameter
            
        Returns:
            Resource path string
        """
        return f"/Devices/{quote(device_id, safe='')}/DOP2/{unit}/{attribute}?idx1={idx1}&idx2={idx2}"

    def parse_leaf_response(self, unit: int, attribute: int, raw_data: bytes) -> Union[Dict[str, Any], List[Any], str, int, float, bytes]:
        """Parse raw DOP2 leaf data using registered parsers.
        
        Args:
            unit: DOP2 unit number
            attribute: DOP2 attribute number
            raw_data: Raw binary data from the leaf
            
        Returns:
            Parsed leaf data (type depends on the specific leaf)
        """
        return parse_leaf(unit, attribute, raw_data)

    def build_sf_value_payload(self, sf_id: int, value: int) -> bytes:
        """Build a binary payload for setting an SF value.
        
        Args:
            sf_id: Setting ID
            value: New value
            
        Returns:
            Binary payload
        """
        payload = write_u16(sf_id) + write_u16(value)
        return payload

    def build_program_selection_payload(self, program_id: int, options: Dict[int, int]) -> bytes:
        """Build a binary payload for program selection.
        
        Args:
            program_id: Program ID
            options: Dictionary mapping option IDs to values
            
        Returns:
            Binary payload
        """
        return build_program_selection(program_id, options)
        
    def detect_generation_from_leaves(self, device_id: str) -> DeviceGenerationType:
        """Detect device generation based on registered leaf access.
        
        This method uses the generation detector's registry to determine
        device generation without making any HTTP calls.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Detected device generation type
        """
        return detector.detect_generation(device_id)
        
    def register_successful_leaf(self, device_id: str, unit: int, attribute: int) -> None:
        """Register a successful leaf access with the generation detector.
        
        Args:
            device_id: Device identifier
            unit: DOP2 unit number  
            attribute: DOP2 attribute number
        """
        detector.register_leaf(device_id, unit, attribute)
        
    def get_leaf_constants(self) -> Dict[str, Tuple[int, int]]:
        """Get all known leaf constants.
        
        Returns:
            Dictionary mapping leaf names to (unit, attribute) tuples
        """
        return {
            # System leaves (Unit 1)
            'SYSTEM_INFO': self.LEAF_SYSTEM_INFO,
            'SYSTEM_STATUS': self.LEAF_SYSTEM_STATUS,
            'SYSTEM_CONFIG': self.LEAF_SYSTEM_CONFIG,
            'SOFTWARE_IDS': self.LEAF_SOFTWARE_IDS,
            
            # Core DOP2 leaves (Unit 2)
            'COMBINED_STATE': self.LEAF_COMBINED_STATE,
            'SF_VALUE': self.LEAF_SF_VALUE,
            'PROGRAM_LIST': self.LEAF_PROGRAM_LIST,
            'HOURS_OF_OPERATION': self.LEAF_HOURS_OF_OPERATION,
            'CYCLE_COUNTER': self.LEAF_CYCLE_COUNTER,
            'CONSUMPTION_STATS': self.LEAF_CONSUMPTION_STATS,
            'DEVICE_STATE': self.LEAF_DEVICE_STATE,
            'DEVICE_IDENT': self.LEAF_DEVICE_IDENT,
            'DEVICE_CONTEXT': self.LEAF_DEVICE_CONTEXT,
            'PS_SELECT': self.LEAF_PS_SELECT,
            'PS_CONTEXT': self.LEAF_PS_CONTEXT,
            'USER_REQUEST': self.LEAF_USER_REQUEST,
            'NOTIFICATION_SHOW': self.LEAF_NOTIFICATION_SHOW,
            'SF_LIST': self.LEAF_SF_LIST,
            'DATE_TIME': self.LEAF_DATE_TIME,
            
            # Semi-pro leaves (Unit 3)
            'SEMIPRO_CONFIG': self.LEAF_SEMIPRO_CONFIG,
            
            # Legacy leaves (Unit 14)
            'LEGACY_PROGRAM_LIST': self.LEAF_LEGACY_PROGRAM_LIST,
            'LEGACY_OPTION_LIST': self.LEAF_LEGACY_OPTION_LIST,
            'LEGACY_STRING_TABLE': self.LEAF_LEGACY_STRING_TABLE,
            
            # File transfer leaves (Unit 15)
            'FT_LAST_UPDATE_INFO': self.LEAF_FT_LAST_UPDATE_INFO,
            'FT_UPDATE_CONTROL': self.LEAF_FT_UPDATE_CONTROL,
            'FT_FILE_INFO': self.LEAF_FT_FILE_INFO,
            'FT_FILE_WRITE': self.LEAF_FT_FILE_WRITE,
            'FT_PUBLIC_KEY': self.LEAF_FT_PUBLIC_KEY,
        }

    def create_explorer(self) -> DOP2Explorer:
        """Create a DOP2Explorer instance that can work with this protocol handler.
        
        Returns:
            DOP2Explorer instance
        """
        return DOP2Explorer()
        
    def parse_program_catalog_primary(self, program_list_data: Any, device_type: str) -> Dict[str, Any]:
        """Parse program catalog from primary method data.
        
        Args:
            program_list_data: Parsed data from leaf 2/1584
            device_type: Device type string
            
        Returns:
            Program catalog dictionary
        """
        if not isinstance(program_list_data, dict) or "programIds" not in program_list_data:
            raise ValueError("Invalid response format from program list leaf 2/1584")
            
        program_ids = program_list_data["programIds"]
        if not program_ids:
            return {"device_type": device_type, "programs": []}
            
        # Build the result structure
        programs = []
        
        # Get options for each program ID
        for pid in program_ids:
            # Basic program structure with ID
            program = {
                "id": pid,
                "name": f"Program_{pid}",  # Default name if no string table
                "options": []
            }
            programs.append(program)
            
        return {
            "device_type": device_type,
            "extraction_method": "dop2_new",
            "programs": programs
        }
        
    def parse_program_catalog_legacy(self, program_list: Any, option_lists: Dict[int, Any], 
                                   string_table: Dict[int, str], device_type: str) -> Dict[str, Any]:
        """Parse program catalog from legacy method data.
        
        Args:
            program_list: Parsed data from leaf 14/1570
            option_lists: Dictionary of parsed option lists by program ID
            string_table: Parsed string table from leaf 14/2570
            device_type: Device type string
            
        Returns:
            Program catalog dictionary
        """
        programs = []
        
        if hasattr(program_list, 'programs'):
            for prog_entry in program_list.programs:
                program = {
                    "id": prog_entry.program_id,
                    "name": string_table.get(prog_entry.name_id, f"Program_{prog_entry.program_id}"),
                    "options": []
                }
                
                # Add options if available
                if prog_entry.program_id in option_lists:
                    option_list = option_lists[prog_entry.program_id]
                    if hasattr(option_list, 'options'):
                        for opt_entry in option_list.options:
                            option = {
                                "id": opt_entry.option_id,
                                "name": string_table.get(opt_entry.name_id, f"Option_{opt_entry.option_id}"),
                                "default": opt_entry.default
                            }
                            program["options"].append(option)
                
                programs.append(program)
        
        return {
            "device_type": device_type,
            "extraction_method": "dop2_legacy", 
            "programs": programs
        }
        
    def build_consumption_stats(self, hours_data: Any, cycles_data: Any, process_data: Any) -> ConsumptionStats:
        """Build ConsumptionStats from individual leaf data.
        
        Args:
            hours_data: Parsed data from hours of operation leaf
            cycles_data: Parsed data from cycle counter leaf  
            process_data: Parsed data from process data leaf
            
        Returns:
            Combined ConsumptionStats object
        """
        hours: Optional[int] = None
        cycles: Optional[int] = None
        energy_wh: Optional[int] = None
        water_l: Optional[int] = None
        
        if isinstance(hours_data, HoursOfOperation):
            hours = hours_data.total_hours
            
        if isinstance(cycles_data, CycleCounter):
            cycles = cycles_data.total_cycles
            
        if isinstance(process_data, ProcessData):
            energy_wh = process_data.energy_wh
            water_l = process_data.water_l
        
        return ConsumptionStats(
            hours_of_operation=hours,
            cycles_completed=cycles,
            energy_wh_total=energy_wh,
            water_l_total=water_l
        ) 