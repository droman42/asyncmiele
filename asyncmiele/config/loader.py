"""Configuration file loading and saving utilities."""

import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

from asyncmiele.models.device_profile import DeviceProfile
from asyncmiele.exceptions.config import CorruptedConfigurationError, InvalidConfigurationError


def save_device_profile(profile: DeviceProfile, path: str) -> None:
    """Save profile to JSON with capability name conversion.
    
    Args:
        profile: The device profile to save
        path: File path to save to
        
    Raises:
        InvalidConfigurationError: If saving fails
    """
    try:
        data = profile.model_dump_json_friendly()
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        raise InvalidConfigurationError(f"Failed to save device profile: {e}")


def load_device_profile(path: str) -> DeviceProfile:
    """Load profile from JSON with capability name conversion.
    
    Args:
        path: File path to load from
        
    Returns:
        The loaded device profile
        
    Raises:
        CorruptedConfigurationError: If the file cannot be read or parsed
        InvalidConfigurationError: If the profile data is invalid
    """
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        return DeviceProfile.from_json_friendly(data)
    except json.JSONDecodeError as e:
        raise CorruptedConfigurationError(f"Invalid JSON in configuration file: {e}")
    except FileNotFoundError:
        raise CorruptedConfigurationError(f"Configuration file not found: {path}")
    except Exception as e:
        raise InvalidConfigurationError(f"Failed to load device profile: {e}")


def backup_device_profile(profile_path: str) -> str:
    """Create a backup of a device profile.
    
    Args:
        profile_path: Path to the profile to backup
        
    Returns:
        Path to the backup file
        
    Raises:
        InvalidConfigurationError: If backup creation fails
    """
    try:
        backup_path = f"{profile_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        import shutil
        shutil.copy2(profile_path, backup_path)
        return backup_path
    except Exception as e:
        raise InvalidConfigurationError(f"Failed to create backup: {e}") 