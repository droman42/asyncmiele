"""Client for interacting with DOP2 protocol on Miele devices.

This module provides the DOP2Client class, which encapsulates all DOP2-specific
operations and knowledge, providing a clean interface for working with the DOP2 protocol.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
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
    """Client for interacting with DOP2 protocol on Miele devices.
    
    This class encapsulates all DOP2-specific operations and knowledge,
    providing a clean interface for working with the DOP2 protocol.
    """
    
    # System leaves (Unit 1)
    LEAF_SYSTEM_INFO = (1, 2)
    LEAF_SYSTEM_STATUS = (1, 3)
    LEAF_SYSTEM_CONFIG = (1, 4)

    # Core DOP2 leaves (Unit 2)
    LEAF_COMBINED_STATE = (2, 256)
    LEAF_SF_VALUE = (2, 105)
    LEAF_PROGRAM_LIST = (2, 1584)
    LEAF_HOURS_OF_OPERATION = (2, 119)
    LEAF_CYCLE_COUNTER = (2, 138)
    LEAF_CONSUMPTION_STATS = (2, 6195)
    LEAF_DEVICE_STATE = (2, 286)
    LEAF_DEVICE_IDENT = (2, 293)

    # Semi-pro leaves (Unit 3)
    LEAF_SEMIPRO_CONFIG = (3, 1000)

    # Legacy leaves (Unit 14)
    LEAF_LEGACY_PROGRAM_LIST = (14, 1570)
    LEAF_LEGACY_OPTION_LIST = (14, 1571)
    LEAF_LEGACY_STRING_TABLE = (14, 2570)
    
    def __init__(self, client):
        """Initialize the DOP2Client.
        
        Args:
            client: MieleClient instance for HTTP communication
        """
        self.client = client
        self._cache = {}  # Optional cache for leaf data

    async def read_leaf(self, device_id: str, unit: int, attribute: int, 
                      idx1: int = 0, idx2: int = 0) -> bytes:
        """Read raw data from a DOP2 leaf.
        
        Args:
            device_id: Device identifier
            unit: DOP2 unit number
            attribute: DOP2 attribute number
            idx1: First index parameter
            idx2: Second index parameter
            
        Returns:
            Raw binary data from the leaf
        """
        path = self._build_leaf_path(device_id, unit, attribute, idx1, idx2)
        result = await self.client._get_raw(path)
        
        # Register successful leaf access with generation detector
        detector.register_leaf(device_id, unit, attribute)
        
        return result

    async def write_leaf(self, device_id: str, unit: int, attribute: int, 
                       payload: bytes, idx1: int = 0, idx2: int = 0) -> None:
        """Write data to a DOP2 leaf.
        
        Args:
            device_id: Device identifier
            unit: DOP2 unit number
            attribute: DOP2 attribute number
            payload: Binary data to write
            idx1: First index parameter
            idx2: Second index parameter
        """
        path = self._build_leaf_path(device_id, unit, attribute, idx1, idx2)
        await self.client._put_request(path, payload)
        
        # Register successful leaf access with generation detector
        detector.register_leaf(device_id, unit, attribute)

    def _build_leaf_path(self, device_id: str, unit: int, attribute: int, 
                       idx1: int, idx2: int) -> str:
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

    async def get_parsed(self, device_id: str, unit: int, attribute: int,
                       idx1: int = 0, idx2: int = 0) -> Any:
        """Get parsed data from a DOP2 leaf.
        
        Args:
            device_id: Device identifier
            unit: DOP2 unit number
            attribute: DOP2 attribute number
            idx1: First index parameter
            idx2: Second index parameter
            
        Returns:
            Parsed leaf data
        """
        raw = await self.read_leaf(device_id, unit, attribute, idx1=idx1, idx2=idx2)
        return parse_leaf(unit, attribute, raw)

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
        
    async def detect_generation(self, device_id: str) -> DeviceGenerationType:
        """Detect the generation of a Miele device.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Detected device generation
        """
        # If we already have leaves registered, use those
        if detector.get_available_leaves(device_id):
            return detector.detect_generation(device_id)
        
        # Otherwise, try to probe some common leaves to determine generation
        try:
            # Try DOP2 leaf
            await self.read_leaf(device_id, *self.LEAF_COMBINED_STATE)
        except Exception:
            pass
        
        try:
            # Try legacy leaf
            await self.read_leaf(device_id, *self.LEAF_LEGACY_PROGRAM_LIST)
        except Exception:
            pass
        
        try:
            # Try semipro leaf
            await self.read_leaf(device_id, *self.LEAF_SEMIPRO_CONFIG)
        except Exception:
            pass
        
        # Now detect based on what succeeded
        return detector.detect_generation(device_id)
        
    async def get_program_catalog(self, device_id: str) -> Dict[str, Any]:
        """Extract program catalog data using correct DOP2 leaves.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Program catalog dictionary
        """
        # Try the primary method first
        try:
            return await self._get_program_catalog_primary(device_id)
        except Exception as e:
            logger.debug(f"Failed to get program catalog using primary method: {e}")
            # Fall back to legacy method
            return await self._get_program_catalog_legacy(device_id)

    async def _get_program_catalog_primary(self, device_id: str) -> Dict[str, Any]:
        """Extract program catalog using leaf 2/1584.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Program catalog dictionary
        """
        # First get the program IDs from the correct leaf
        program_list_data = await self.get_parsed(device_id, *self.LEAF_PROGRAM_LIST)
        
        if not isinstance(program_list_data, dict) or "programIds" not in program_list_data:
            raise ValueError("Invalid response format from program list leaf 2/1584")
            
        program_ids = program_list_data["programIds"]
        if not program_ids:
            return {"device_type": "unknown", "programs": []}
            
        # Get device info for the device type
        ident = await self.client.get_device_ident(device_id)
        if isinstance(ident.device_type, int):
            try:
                device_type = DeviceType(ident.device_type).name
            except ValueError:
                device_type = f"unknown_{ident.device_type}"
        else:
            device_type = ident.device_type or ident.tech_type or "unknown"
            
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
            
            # Try to get options using leaf 2/105 with program ID as index
            try:
                options_data = await self.get_parsed(device_id, *self.LEAF_SF_VALUE, idx1=pid)
                if isinstance(options_data, dict) and "options" in options_data:
                    program["options"] = options_data["options"]
            except Exception:
                # If options can't be retrieved, continue with empty options list
                pass
                
            programs.append(program)
            
        return {
            "device_type": device_type,
            "programs": programs
        }

    async def _get_program_catalog_legacy(self, device_id: str) -> Dict[str, Any]:
        """Extract program catalog using legacy leaves 14/1570, 14/1571, and 14/2570.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Program catalog dictionary
        """
        try:
            # First try with the old leaf IDs
            leaf_1570 = await self.read_leaf(device_id, *self.LEAF_LEGACY_PROGRAM_LIST)
            
            programs = parse_program_list(leaf_1570)
            
            # Get options for each program
            for prog in programs:
                pid = prog["id"]
                leaf_1571 = await self.read_leaf(device_id, *self.LEAF_LEGACY_OPTION_LIST, idx1=pid)
                prog["options"] = parse_option_list(leaf_1571)
            
            # Resolve string names
            string_blob = await self.read_leaf(device_id, *self.LEAF_LEGACY_STRING_TABLE)
            str_map = build_string_map(string_blob)
            
            for p in programs:
                p["name"] = str_map.get(p.pop("name_id", 0), f"program_{p['id']}")
                for opt in p["options"]:
                    opt["name"] = str_map.get(opt.pop("name_id", 0), f"opt_{opt['id']}")
            
            # Get device type
            ident = await self.client.get_device_ident(device_id)
            if isinstance(ident.device_type, int):
                try:
                    device_type = DeviceType(ident.device_type).name
                except ValueError:
                    device_type = f"unknown_{ident.device_type}"
            else:
                device_type = ident.device_type or ident.tech_type or "unknown"
                
            return {
                "device_type": device_type,
                "programs": programs
            }
        except Exception as e:
            logger.debug(f"Failed to get program catalog using legacy method: {e}")
            # If the old way fails, return empty catalog
            return {"device_type": "unknown", "programs": []}
            
    async def get_consumption_stats(self, device_id: str) -> ConsumptionStats:
        """Get consumption statistics for a device.
        
        Args:
            device_id: Device identifier
            
        Returns:
            ConsumptionStats object
        """
        hours: Optional[int] = None
        cycles: Optional[int] = None
        energy_wh: Optional[int] = None
        water_l: Optional[int] = None
        
        try:
            hours_result = await self.get_parsed(device_id, *self.LEAF_HOURS_OF_OPERATION)
            if isinstance(hours_result, HoursOfOperation):
                hours = hours_result.total_hours
        except Exception:
            pass
        
        try:
            cycles_result = await self.get_parsed(device_id, *self.LEAF_CYCLE_COUNTER)
            if isinstance(cycles_result, CycleCounter):
                cycles = cycles_result.total_cycles
        except Exception:
            pass
        
        try:
            process_data = await self.get_parsed(device_id, *self.LEAF_CONSUMPTION_STATS)
            if isinstance(process_data, ProcessData):
                energy_wh = process_data.energy_wh
                water_l = process_data.water_l
        except Exception:
            pass
        
        return ConsumptionStats(
            hours_of_operation=hours,
            cycles_completed=cycles,
            energy_wh_total=energy_wh,
            water_l_total=water_l
        )
        
    async def get_setting(self, device_id: str, sf_id: int) -> SFValue:
        """Get a setting value.
        
        Args:
            device_id: Device identifier
            sf_id: Setting ID
            
        Returns:
            SFValue object
        """
        parsed = await self.get_parsed(device_id, *self.LEAF_SF_VALUE, idx1=sf_id)
        if not isinstance(parsed, SFValue):
            raise ValueError("Leaf did not return SFValue structure")
        return parsed

    async def set_setting(self, device_id: str, sf_id: int, new_value: int) -> None:
        """Set a setting value.
        
        Args:
            device_id: Device identifier
            sf_id: Setting ID
            new_value: New value to set
        """
        sf = await self.get_setting(device_id, sf_id)
        
        if not (sf.minimum <= new_value <= sf.maximum):
            raise ValueError(f"Value {new_value} outside allowed range {sf.range}")
        
        payload = self.build_sf_value_payload(sf_id, new_value)
        await self.write_leaf(device_id, *self.LEAF_SF_VALUE, payload, idx1=sf_id)
        
    def get_explorer(self) -> DOP2Explorer:
        """Get a DOP2Explorer instance configured with this client.
        
        Returns:
            DOP2Explorer instance
        """
        return DOP2Explorer(self) 