"""Configuration utilities for asyncmiele."""

from dataclasses import dataclass, field
from .loader import save_device_profile, load_device_profile, backup_device_profile


@dataclass
class _Settings:
    """Global settings for asyncmiele runtime.

    Attributes
    ----------
    enable_remote_start
        When *True* the :pymeth:`MieleClient.remote_start` helper is allowed to
        trigger a program start.  Default is *False* for safety.
    """

    enable_remote_start: bool = field(default=False)


# single shared instance -------------------------------------------------------
settings = _Settings()

__all__ = ['save_device_profile', 'load_device_profile', 'backup_device_profile', 'settings'] 