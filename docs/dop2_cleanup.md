# DOP2 Cleanup and Refactoring Plan

This document outlines the plan for refactoring the DOP2 functionality in the asyncmiele library to achieve better separation of concerns, reduce code duplication, and improve maintainability.

## Current Issues

The current implementation has several issues that need to be addressed:

### 1. Separation of Concerns

The MieleClient class currently handles both HTTP communication and DOP2-specific operations, which violates the principle of separation of concerns. DOP2-specific functionality should be isolated in the dop2 package.

### 2. Code Duplication

There is significant duplication between MieleClient and the dop2 package:

- Leaf address knowledge is duplicated
- Binary payload construction appears in multiple places
- Parsing logic is repeated
- Parameter defaults are defined in multiple locations
- Generation detection logic is duplicated

### 3. Architectural Issues

- Circular dependencies between MieleClient and dop2 components
- Inconsistent abstraction levels across the codebase
- Scattered DOP2 protocol knowledge
- Inconsistent parameter handling

## Refactoring Plan

The refactoring will be executed in three phases:

## Phase 1: Foundation - Create DOP2Client and Core Infrastructure ✅

### Goals
- Create the DOP2Client class with core functionality ✅
- Establish clear interfaces between components ✅
- Define the architecture for clean separation of concerns ✅

### Detailed Steps

#### 1.1 Create DOP2Client Class ✅

Create a new file `asyncmiele/dop2/client.py` with the DOP2Client class:

```python
class DOP2Client:
    """Client for interacting with DOP2 protocol on Miele devices.
    
    This class encapsulates all DOP2-specific operations and knowledge,
    providing a clean interface for working with the DOP2 protocol.
    """
    
    def __init__(self, client):
        """Initialize the DOP2Client.
        
        Args:
            client: MieleClient instance for HTTP communication
        """
        self.client = client
        self._cache = {}  # Optional cache for leaf data
```

#### 1.2 Implement Core Leaf Operations ✅

Add methods for reading and writing DOP2 leaves:

```python
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
    from asyncmiele.dop2.generation import detector
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
    from asyncmiele.dop2.generation import detector
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
    from urllib.parse import quote
    return f"/Devices/{quote(device_id, safe='')}/DOP2/{unit}/{attribute}?idx1={idx1}&idx2={idx2}"
```

#### 1.3 Implement Parsed Leaf Access ✅

Add method for getting parsed leaf data:

```python
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
    from asyncmiele.dop2.parser import parse_leaf
    return parse_leaf(unit, attribute, raw)
```

#### 1.4 Define Leaf Address Constants ✅

Create constants for all known DOP2 leaf addresses:

```python
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
```

#### 1.5 Implement Binary Payload Construction ✅

Add methods for constructing binary payloads:

```python
def build_sf_value_payload(self, sf_id: int, value: int) -> bytes:
    """Build a binary payload for setting an SF value.
    
    Args:
        sf_id: Setting ID
        value: New value
        
    Returns:
        Binary payload
    """
    from asyncmiele.dop2.binary import write_u16
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
    from asyncmiele.dop2.programs import build_program_selection
    return build_program_selection(program_id, options)
```

#### 1.6 Add Factory Method to MieleClient ✅

Add a method to MieleClient to create a DOP2Client instance:

```python
def get_dop2_client(self) -> "DOP2Client":
    """Get a DOP2Client instance configured with this client.
    
    Returns:
        DOP2Client instance
    """
    from asyncmiele.dop2.client import DOP2Client
    return DOP2Client(self)
```

#### 1.7 Create Initial Tests ✅

Create tests for the DOP2Client in `tests/test_dop2_client.py`:

- Test leaf reading/writing ✅
- Test parsed leaf access ✅
- Test binary payload construction ✅
- Test integration with generation detector ✅

### Deliverables for Phase 1 ✅

- New `asyncmiele/dop2/client.py` file with DOP2Client class ✅
- Constants and documentation for DOP2 protocol ✅
- Factory method in MieleClient ✅
- Initial test suite for DOP2Client ✅

## Phase 2: Migration - Move Functionality to DOP2Client ✅

### Goals
- Implement all DOP2 operations in DOP2Client ✅
- Update DOP2Explorer and DOP2Visualizer to work with DOP2Client ✅
- Prepare for complete removal of DOP2 functionality from MieleClient ✅

### Detailed Steps

#### 2.1 Implement Generation Detection ✅

Add generation detection to DOP2Client:

```python
async def detect_generation(self, device_id: str) -> DeviceGenerationType:
    """Detect the generation of a Miele device.
    
    Args:
        device_id: Device identifier
        
    Returns:
        Detected device generation
    """
    from asyncmiele.dop2.generation import detector
    
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
```

#### 2.2 Implement Program Catalog Extraction ✅

Add program catalog extraction to DOP2Client:

```python
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
        # Fall back to legacy method
        return await self._get_program_catalog_legacy(device_id)

async def _get_program_catalog_primary(self, device_id: str) -> Dict[str, Any]:
    """Extract program catalog using leaf 2/1584.
    
    Args:
        device_id: Device identifier
        
    Returns:
        Program catalog dictionary
    """
    # Implementation details...

async def _get_program_catalog_legacy(self, device_id: str) -> Dict[str, Any]:
    """Extract program catalog using legacy leaves 14/1570, 14/1571, and 14/2570.
    
    Args:
        device_id: Device identifier
        
    Returns:
        Program catalog dictionary
    """
    # Implementation details...
```

#### 2.3 Implement Consumption Statistics ✅

Add consumption statistics to DOP2Client:

```python
async def get_consumption_stats(self, device_id: str) -> ConsumptionStats:
    """Get consumption statistics for a device.
    
    Args:
        device_id: Device identifier
        
    Returns:
        ConsumptionStats object
    """
    # Implementation details...
```

#### 2.4 Implement Settings Management ✅

Add settings management to DOP2Client:

```python
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
```

#### 2.5 Update DOP2Explorer ✅

Modify DOP2Explorer to work with DOP2Client:

```python
class DOP2Explorer:
    """Explorer for DOP2 tree structures."""
    
    def __init__(self, client_or_dop2client):
        """Initialize the explorer.
        
        Args:
            client_or_dop2client: MieleClient or DOP2Client instance
        """
        if hasattr(client_or_dop2client, 'read_leaf'):
            # It's already a DOP2Client
            self.dop2_client = client_or_dop2client
        else:
            # It's a MieleClient, get a DOP2Client from it
            self.dop2_client = client_or_dop2client.get_dop2_client()
            
        # Rest of initialization...
```

Update all methods to use DOP2Client instead of directly accessing MieleClient.

#### 2.6 Update DOP2Visualizer ✅

Ensure DOP2Visualizer works with the new architecture:

```python
def visualize_from_json(json_file: str, output_file: Optional[str] = None, 
                       format_type: str = 'html') -> Optional[str]:
    """Visualize a DOP2 tree from a JSON file.
    
    Args:
        json_file: Path to JSON file containing tree data
        output_file: Path to save the visualization (optional)
        format_type: Type of visualization to generate ('html' or 'ascii')
        
    Returns:
        Visualization string if output_file is None, otherwise None
    """
    # Import here to avoid circular imports
    from .explorer import DOP2Explorer
    
    # Load tree from JSON
    tree = asyncio.run(DOP2Explorer.import_tree_from_json(json_file))
    
    # Visualize tree
    return visualize_tree(tree, output_file, format_type)
```

#### 2.7 Expand Test Coverage ✅

Create comprehensive tests for all DOP2Client operations:
- Test generation detection ✅
- Test program catalog extraction ✅
- Test consumption statistics ✅
- Test settings management ✅
- Test integration with Explorer and Visualizer ✅

### Deliverables for Phase 2 ✅

- Fully functional DOP2Client with all DOP2 operations ✅
- Updated DOP2Explorer and DOP2Visualizer ✅
- Comprehensive test suite for new components ✅
- Integration tests for the complete DOP2 package ✅

## Phase 3: Completion - Refactor MieleClient and Update Public API

### Goals
- Remove all DOP2 functionality from MieleClient
- Update MieleClient to delegate to DOP2Client
- Update all examples and documentation
- Ensure clean public API

### Detailed Steps

#### 3.1 Remove DOP2 Methods from MieleClient

Remove these methods from MieleClient:
- `_dop2_path`
- `dop2_read_leaf`
- `dop2_write_leaf`
- `dop2_get_parsed`

#### 3.2 Update Public API Methods

Update these methods to use DOP2Client:

```python
async def detect_device_generation(self, device_id: str) -> DeviceGenerationType:
    """Detect the generation of a Miele device.
    
    Args:
        device_id: Device identifier
        
    Returns:
        Detected device generation
    """
    dop2_client = self.get_dop2_client()
    return await dop2_client.detect_generation(device_id)

async def get_program_catalog(self, device_id: str) -> Dict[str, Any]:
    """Extract the program catalog from a device.
    
    Args:
        device_id: Device identifier
        
    Returns:
        Program catalog dictionary
    """
    dop2_client = self.get_dop2_client()
    return await dop2_client.get_program_catalog(device_id)

async def get_consumption_stats(self, device_id: str) -> ConsumptionStats:
    """Get consumption statistics for a device.
    
    Args:
        device_id: Device identifier
        
    Returns:
        ConsumptionStats object
    """
    dop2_client = self.get_dop2_client()
    return await dop2_client.get_consumption_stats(device_id)

async def get_setting(self, device_id: str, sf_id: int) -> SFValue:
    """Get a setting value.
    
    Args:
        device_id: Device identifier
        sf_id: Setting ID
        
    Returns:
        SFValue object
    """
    dop2_client = self.get_dop2_client()
    return await dop2_client.get_setting(device_id, sf_id)

async def set_setting(self, device_id: str, sf_id: int, new_value: int) -> None:
    """Set a setting value.
    
    Args:
        device_id: Device identifier
        sf_id: Setting ID
        new_value: New value to set
    """
    dop2_client = self.get_dop2_client()
    await dop2_client.set_setting(device_id, sf_id, new_value)
```

#### 3.3 Update DOP2 Tree Exploration Methods

Update these methods to use DOP2Client:

```python
async def explore_dop2_tree(
    self,
    device_id: str,
    max_unit: int = 20,
    max_attribute: int = 10000,
    known_only: bool = False,
    concurrency: int = 3
) -> "DOP2Tree":
    """Explore the DOP2 tree structure of a device.
    
    Args:
        device_id: Device identifier
        max_unit: Maximum unit ID to try
        max_attribute: Maximum attribute ID to try
        known_only: If True, only explore known leaf attributes
        concurrency: Maximum number of concurrent requests
        
    Returns:
        DOP2Tree object containing the complete tree structure
    """
    dop2_client = self.get_dop2_client()
    explorer = dop2_client.get_explorer()
    return await explorer.explore_device(
        device_id,
        max_unit=max_unit,
        max_attribute=max_attribute,
        known_only=known_only,
        concurrency=concurrency
    )
```

#### 3.4 Update All Examples

Update all example scripts to use the new approach:

```python
# Before
client = MieleClient(...)
leaf_data = await client.dop2_read_leaf(device_id, 2, 256)

# After
client = MieleClient(...)
dop2_client = client.get_dop2_client()
leaf_data = await dop2_client.read_leaf(device_id, 2, 256)
```

Create new examples demonstrating best practices:

```python
# Example: Using DOP2Client for advanced operations
async def advanced_dop2_example():
    client = MieleClient(...)
    dop2_client = client.get_dop2_client()
    
    # Get device generation
    generation = await dop2_client.detect_generation(device_id)
    print(f"Device generation: {generation}")
    
    # Read multiple leaves efficiently
    tasks = [
        dop2_client.get_parsed(device_id, 2, 256),  # Combined state
        dop2_client.get_parsed(device_id, 2, 105, idx1=10),  # Setting value
    ]
    results = await asyncio.gather(*tasks)
    
    # Process results
    combined_state, setting = results
    print(f"Combined state: {combined_state}")
    print(f"Setting: {setting}")
```

#### 3.5 Comprehensive Documentation Update

Update all documentation to reflect the new architecture:

- Update API documentation
- Create guides for working with DOP2Client
- Document best practices
- Update examples in documentation

#### 3.6 Final Testing and Validation

Ensure all tests pass with the new architecture:

- Unit tests for DOP2Client
- Integration tests for the complete DOP2 package
- End-to-end tests with real devices
- Performance testing to ensure no regressions

### Deliverables for Phase 3

- Fully refactored MieleClient with clean separation of concerns
- Updated examples and documentation
- Complete test coverage
- Clean public API

## Timeline and Dependencies

### Phase 1 Dependencies
- Understanding of current DOP2 implementation
- Clear interface definitions
- Agreement on architecture

### Phase 2 Dependencies
- Completion of Phase 1
- Comprehensive test suite for DOP2Client
- Functional equivalence with current implementation

### Phase 3 Dependencies
- Completion of Phase 2
- Full test coverage of new components
- Agreement on public API design

## Benefits of This Refactoring

- **Cleaner Separation of Concerns**: Each class has a clear responsibility
- **Reduced Duplication**: DOP2 knowledge is centralized in one place
- **Better Testability**: Components can be tested in isolation
- **Improved Maintainability**: Changes to DOP2 handling only affect one class
- **Consistent Parameter Handling**: Default parameters defined in one place
- **No Circular Dependencies**: Clear dependency direction from MieleClient to DOP2Client

## Conclusion

This refactoring plan provides a clear path to improving the architecture of the asyncmiele library by properly separating DOP2 functionality from the MieleClient class. By centralizing DOP2 knowledge in the DOP2Client class, we reduce duplication, improve maintainability, and create a more testable codebase.

The three-phase approach allows for incremental improvement while ensuring that each phase delivers tangible benefits. The end result will be a cleaner, more maintainable library with better separation of concerns. 