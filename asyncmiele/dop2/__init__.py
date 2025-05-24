"""DOP2 protocol support for Miele devices.

This package provides functionality for working with the DOP2 (Device Operation Protocol v2)
used by Miele appliances for local control and status reporting.
"""

from .models import (
    DeviceCombinedState, SFValue, TariffConfig, ConsumptionStats,
    DeviceIdent, DateTime, DeviceContext, ProgramSelection,
    ProgramList, ProgramListEntry, OptionList, OptionListEntry,
    DeviceState, ProcessData, SFList, NotificationShow,
    HoursOfOperation, CycleCounter, SoftwareIds, NetworkConfig,
    DeviceGenerationType, DOP2Node, DOP2Tree
)

from .parser import (
    parse_leaf, detect_device_generation,
    register_parser
)

from .binary import (
    read_u8, read_u16, read_u32, read_s8, read_s16, read_s32,
    read_float, read_string, read_bytes,
    write_u8, write_u16, write_u32, write_s8, write_s16, write_s32,
    write_float, write_string, pad_to_block_size, unpad
)

from .programs import (
    parse_program_list, parse_option_list, build_string_map,
    parse_program_list_from_leaf_2_1584, build_program_selection
)

from .generation import GenerationDetector, detector

from .explorer import (
    DOP2Explorer, explorer, set_client, KNOWN_LEAVES,
    MAX_ATTRIBUTE_ID, MAX_EMPTY_LEAVES
)

from .visualizer import (
    DOP2Visualizer, visualize_tree, visualize_from_json
)

from .client import DOP2Client

__all__ = [
    # Models
    "DeviceCombinedState", "SFValue", "TariffConfig", "ConsumptionStats",
    "DeviceIdent", "DateTime", "DeviceContext", "ProgramSelection",
    "ProgramList", "ProgramListEntry", "OptionList", "OptionListEntry",
    "DeviceState", "ProcessData", "SFList", "NotificationShow",
    "HoursOfOperation", "CycleCounter", "SoftwareIds", "NetworkConfig",
    "DeviceGenerationType", "DOP2Node", "DOP2Tree",
    
    # Parser functions
    "parse_leaf", "detect_device_generation",
    "register_parser",
    
    # Binary utilities
    "read_u8", "read_u16", "read_u32", "read_s8", "read_s16", "read_s32",
    "read_float", "read_string", "read_bytes",
    "write_u8", "write_u16", "write_u32", "write_s8", "write_s16", "write_s32",
    "write_float", "write_string", "pad_to_block_size", "unpad",
    
    # Program utilities
    "parse_program_list", "parse_option_list", "build_string_map",
    "parse_program_list_from_leaf_2_1584", "build_program_selection",
    
    # Generation detection
    "GenerationDetector", "detector",
    
    # Tree explorer
    "DOP2Explorer", "explorer", "set_client", "KNOWN_LEAVES",
    "MAX_ATTRIBUTE_ID", "MAX_EMPTY_LEAVES",
    
    # Tree visualizer
    "DOP2Visualizer", "visualize_tree", "visualize_from_json",
    
    # DOP2 Client
    "DOP2Client"
] 