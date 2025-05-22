"""
Credentials models for Miele device authentication.
"""

import secrets
import re
from typing import Optional, Union, ClassVar

from pydantic import BaseModel, Field, field_validator, model_validator

class MieleCredentials(BaseModel):
    """
    Credentials for authenticating with Miele devices.
    
    Handles validation and conversion between hex strings and bytes for GroupID and GroupKey.
    """
    # Regular expression for validating hex strings
    HEX_PATTERN: ClassVar[re.Pattern] = re.compile(r'^[0-9a-fA-F]+$')
    
    # GroupID is a 16-character (8 bytes) hex string
    group_id: Union[str, bytes] = Field(
        description="GroupID for Miele authentication (8 bytes, 16 hex chars)"
    )
    
    # GroupKey is a 128-character (64 bytes) hex string
    group_key: Union[str, bytes] = Field(
        description="GroupKey for Miele authentication (64 bytes, 128 hex chars)"
    )
    
    # Internal storage as bytes
    _group_id_bytes: Optional[bytes] = None
    _group_key_bytes: Optional[bytes] = None
    
    @field_validator('group_id')
    @classmethod
    def validate_group_id(cls, v: Union[str, bytes]) -> Union[str, bytes]:
        """Validate GroupID format."""
        if isinstance(v, bytes):
            if len(v) != 8:
                raise ValueError(f"GroupID must be 8 bytes, got {len(v)}")
            return v
        
        if not isinstance(v, str):
            raise ValueError(f"GroupID must be a string or bytes, got {type(v)}")
        
        if not cls.HEX_PATTERN.match(v):
            raise ValueError("GroupID must contain only hexadecimal characters")
        
        if len(v) != 16:
            raise ValueError(f"GroupID must be 16 hex characters, got {len(v)}")
            
        return v
    
    @field_validator('group_key')
    @classmethod
    def validate_group_key(cls, v: Union[str, bytes]) -> Union[str, bytes]:
        """Validate GroupKey format."""
        if isinstance(v, bytes):
            if len(v) != 64:
                raise ValueError(f"GroupKey must be 64 bytes, got {len(v)}")
            return v
        
        if not isinstance(v, str):
            raise ValueError(f"GroupKey must be a string or bytes, got {type(v)}")
        
        if not cls.HEX_PATTERN.match(v):
            raise ValueError("GroupKey must contain only hexadecimal characters")
        
        if len(v) != 128:
            raise ValueError(f"GroupKey must be 128 hex characters, got {len(v)}")
            
        return v
    
    @model_validator(mode='after')
    def convert_to_bytes(self) -> 'MieleCredentials':
        """Convert hex strings to bytes for internal storage."""
        if isinstance(self.group_id, str):
            self._group_id_bytes = bytes.fromhex(self.group_id)
        else:
            self._group_id_bytes = self.group_id
            
        if isinstance(self.group_key, str):
            self._group_key_bytes = bytes.fromhex(self.group_key)
        else:
            self._group_key_bytes = self.group_key
            
        return self
    
    def get_id_bytes(self) -> bytes:
        """Get GroupID as bytes."""
        return self._group_id_bytes
    
    def get_key_bytes(self) -> bytes:
        """Get GroupKey as bytes."""
        return self._group_key_bytes
    
    def get_id_hex(self) -> str:
        """Get GroupID as hex string."""
        if isinstance(self.group_id, str):
            return self.group_id
        return self._group_id_bytes.hex()
    
    def get_key_hex(self) -> str:
        """Get GroupKey as hex string."""
        if isinstance(self.group_key, str):
            return self.group_key
        return self._group_key_bytes.hex()
    
    def model_dump_json(self, **kwargs) -> str:
        """Export to JSON with hex string representation."""
        return super().model_dump_json(**kwargs)
    
    def model_dump(self, **kwargs) -> dict:
        """Export to dict with hex string representation."""
        return super().model_dump(**kwargs)
    
    @classmethod
    def generate_random(cls) -> 'MieleCredentials':
        """
        Generate random credentials for device provisioning.
        
        Returns:
            MieleCredentials: New random credentials
        """
        group_id = secrets.token_hex(8)  # 16 hex chars
        group_key = secrets.token_hex(64)  # 128 hex chars
        return cls(group_id=group_id, group_key=group_key) 