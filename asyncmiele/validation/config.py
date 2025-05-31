"""Configuration validation system."""

import asyncio
from typing import List, Optional, Any, Protocol
from dataclasses import dataclass

from asyncmiele.models.device_profile import DeviceProfile
from asyncmiele.capabilities import DeviceCapability
from asyncmiele.exceptions.config import InvalidConfigurationError


class ClientProtocol(Protocol):
    """Protocol defining the interface we need from MieleClient."""
    
    async def get_device(self, device_id: str) -> Any:
        """Get device by ID."""
        ...
    
    async def wake_up(self, device_id: str) -> None:
        """Wake up device."""
        ...
    
    async def get_device_state(self, device_id: str) -> Any:
        """Get device state."""
        ...
    
    async def can_remote_start(self, device_id: str) -> bool:
        """Check if device can remote start."""
        ...
    
    async def get_program_catalog(self, device_id: str) -> Any:
        """Get program catalog."""
        ...
    
    async def __aenter__(self) -> "ClientProtocol":
        """Async context manager entry."""
        ...
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        ...


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    success: bool
    issues: List[str]
    connection: bool
    capability_issues: List[str]
    catalog_available: bool


class ConfigurationValidator:
    """Validates device profile configurations."""
    
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
    
    async def validate_profile(self, profile: DeviceProfile, client: ClientProtocol) -> ValidationResult:
        """Validate complete device profile.
        
        Args:
            profile: The device profile to validate
            client: MieleClient instance to use for validation
            
        Returns:
            ValidationResult with detailed validation information
        """
        issues = []
        
        # Validate model structure
        try:
            profile.model_validate(profile.model_dump())
        except Exception as e:
            issues.append(f"Invalid profile structure: {e}")
        
        # Test connectivity
        connection_ok = await self.validate_connectivity(profile, client)
        if not connection_ok:
            issues.append("Cannot connect to device")
        
        # Validate capabilities
        capability_issues = await self.validate_capabilities(profile, client) if connection_ok else []
        
        # Check program catalog
        catalog_available = self.validate_program_catalog(profile)
        if not catalog_available:
            issues.append("No program catalog available")
        
        return ValidationResult(
            success=len(issues) == 0 and connection_ok and len(capability_issues) == 0,
            issues=issues,
            connection=connection_ok,
            capability_issues=capability_issues,
            catalog_available=catalog_available
        )
    
    async def validate_connectivity(self, profile: DeviceProfile, client: ClientProtocol) -> bool:
        """Test device connectivity.
        
        Args:
            profile: The device profile to test
            client: MieleClient instance to use for testing
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            async with client:
                await client.get_device(profile.device_id)
            return True
        except Exception:
            return False
    
    async def validate_capabilities(self, profile: DeviceProfile, client: ClientProtocol) -> List[str]:
        """Validate device capabilities.
        
        Args:
            profile: The device profile to validate
            client: MieleClient instance to use for testing
            
        Returns:
            List of capability validation issues
        """
        issues = []
        
        try:
            async with client:
                for capability in profile.capabilities:
                    try:
                        # Test each capability
                        await self._test_capability(client, profile.device_id, capability)
                    except Exception as e:
                        issues.append(f"{capability.name}: {e}")
        except Exception as e:
            issues.append(f"Failed to test capabilities: {e}")
        
        return issues
    
    def validate_program_catalog(self, profile: DeviceProfile) -> bool:
        """Check program catalog availability.
        
        Args:
            profile: The device profile to check
            
        Returns:
            True if catalog is available and valid, False otherwise
        """
        return profile.program_catalog is not None and len(profile.program_catalog.get("programs", {})) > 0
    
    async def _test_capability(self, client: ClientProtocol, device_id: str, capability: DeviceCapability) -> None:
        """Test a specific capability.
        
        Args:
            client: The Miele client to use for testing
            device_id: Device ID to test
            capability: Capability to test
            
        Raises:
            Exception: If the capability test fails
        """
        # Basic capability tests - simplified for validation
        if capability == DeviceCapability.WAKE_UP:
            await client.wake_up(device_id)
        elif capability == DeviceCapability.STATE_REPORTING:
            await client.get_device_state(device_id)
        elif capability == DeviceCapability.REMOTE_START:
            await client.can_remote_start(device_id)
        elif capability == DeviceCapability.PROGRAM_CATALOG:
            catalog = await client.get_program_catalog(device_id)
            if not catalog or not catalog.get("programs"):
                raise Exception("Program catalog extraction returned empty result")
        # For other capabilities, we just pass - validation is basic
        pass 