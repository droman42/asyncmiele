"""Device generation detection for Miele appliances.

This module provides functionality to detect and handle different generations
of Miele device DOP2 implementations (legacy/dop1, dop2, semipro).
"""

import logging
from typing import Dict, Any, Optional, Set, List

from .models import DeviceGenerationType

logger = logging.getLogger(__name__)

# Leaf availability patterns for different device generations
# These are sets of (unit, attribute) tuples that are characteristic of each generation
_LEGACY_LEAVES: Set[tuple] = {
    (14, 1570),  # Legacy program list
    (14, 1571),  # Legacy option list
    (14, 2570),  # Legacy string table
}

_DOP2_LEAVES: Set[tuple] = {
    (2, 256),    # Device combined state
    (2, 105),    # SF Value
    (2, 1584),   # Program list (newer format)
}

_SEMIPRO_LEAVES: Set[tuple] = {
    (2, 256),    # Device combined state
    (2, 105),    # SF Value
    (2, 1584),   # Program list (newer format)
    (3, 1000),   # Semi-pro specific leaf
}


class GenerationDetector:
    """Detector for Miele device generations.
    
    This class provides functionality to detect which generation a device belongs to
    based on its available DOP2 leaves and response patterns.
    """
    
    def __init__(self):
        """Initialize the detector."""
        self._device_generations: Dict[str, DeviceGenerationType] = {}
        self._available_leaves: Dict[str, Set[tuple]] = {}
    
    def register_leaf(self, device_id: str, unit: int, attribute: int) -> None:
        """Register that a leaf is available for a device.
        
        Args:
            device_id: Device identifier
            unit: DOP2 unit number
            attribute: DOP2 attribute number
        """
        if device_id not in self._available_leaves:
            self._available_leaves[device_id] = set()
        
        self._available_leaves[device_id].add((unit, attribute))
        
        # Clear cached generation when new leaves are discovered
        if device_id in self._device_generations:
            del self._device_generations[device_id]
    
    def detect_generation(self, device_id: str) -> DeviceGenerationType:
        """Detect the generation of a device based on its available leaves.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Detected device generation type
        """
        # Return cached result if available
        if device_id in self._device_generations:
            return self._device_generations[device_id]
        
        # If no leaves registered yet, default to DOP2
        if device_id not in self._available_leaves:
            return DeviceGenerationType.DOP2
        
        available = self._available_leaves[device_id]
        
        # Check for semipro first (most specific)
        if any((unit, attr) in available for (unit, attr) in _SEMIPRO_LEAVES):
            generation = DeviceGenerationType.SEMIPRO
        # Then check for standard DOP2
        elif any((unit, attr) in available for (unit, attr) in _DOP2_LEAVES):
            generation = DeviceGenerationType.DOP2
        # Finally check for legacy
        elif any((unit, attr) in available for (unit, attr) in _LEGACY_LEAVES):
            generation = DeviceGenerationType.LEGACY
        # Default to DOP2 if we can't determine
        else:
            generation = DeviceGenerationType.DOP2
        
        # Cache the result
        self._device_generations[device_id] = generation
        return generation
    
    def get_available_leaves(self, device_id: str) -> List[tuple]:
        """Get the list of available leaves for a device.
        
        Args:
            device_id: Device identifier
            
        Returns:
            List of (unit, attribute) tuples for available leaves
        """
        if device_id not in self._available_leaves:
            return []
        
        return list(self._available_leaves[device_id])
    
    def clear_cache(self, device_id: Optional[str] = None) -> None:
        """Clear the cached generation detection results.
        
        Args:
            device_id: If provided, clear only for this device; otherwise clear all
        """
        if device_id:
            if device_id in self._device_generations:
                del self._device_generations[device_id]
        else:
            self._device_generations.clear()


# Global instance for shared use
detector = GenerationDetector() 