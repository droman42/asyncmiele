"""Binary parsing utilities for DOP2 protocol.

This module provides standardized functions for binary data manipulation
used in DOP2 protocol parsing and encoding.
"""

import struct
from typing import List, Tuple, Dict, Any, Optional


# Common struct formats
U8 = struct.Struct('>B')    # unsigned byte
U16 = struct.Struct('>H')   # unsigned short (16-bit)
U32 = struct.Struct('>I')   # unsigned int (32-bit)
S8 = struct.Struct('>b')    # signed byte
S16 = struct.Struct('>h')   # signed short (16-bit)
S32 = struct.Struct('>i')   # signed int (32-bit)
FLOAT = struct.Struct('>f') # 32-bit float


def read_u8(data: bytes, offset: int = 0) -> int:
    """Read an unsigned 8-bit integer from data at offset."""
    return U8.unpack_from(data, offset)[0]


def read_u16(data: bytes, offset: int = 0) -> int:
    """Read an unsigned 16-bit integer from data at offset."""
    return U16.unpack_from(data, offset)[0]


def read_u32(data: bytes, offset: int = 0) -> int:
    """Read an unsigned 32-bit integer from data at offset."""
    return U32.unpack_from(data, offset)[0]


def read_s8(data: bytes, offset: int = 0) -> int:
    """Read a signed 8-bit integer from data at offset."""
    return S8.unpack_from(data, offset)[0]


def read_s16(data: bytes, offset: int = 0) -> int:
    """Read a signed 16-bit integer from data at offset."""
    return S16.unpack_from(data, offset)[0]


def read_s32(data: bytes, offset: int = 0) -> int:
    """Read a signed 32-bit integer from data at offset."""
    return S32.unpack_from(data, offset)[0]


def read_float(data: bytes, offset: int = 0) -> float:
    """Read a 32-bit float from data at offset."""
    return FLOAT.unpack_from(data, offset)[0]


def read_string(data: bytes, offset: int = 0, max_length: Optional[int] = None) -> str:
    """Read a null-terminated string from data at offset.
    
    Args:
        data: Bytes to read from
        offset: Starting position
        max_length: Maximum string length to read
        
    Returns:
        UTF-8 decoded string
    """
    if max_length is not None:
        end = data.find(b'\x00', offset, offset + max_length)
    else:
        end = data.find(b'\x00', offset)
        
    if end == -1:
        # No null terminator found, use all remaining data
        if max_length is not None:
            end = min(offset + max_length, len(data))
        else:
            end = len(data)
    
    return data[offset:end].decode('utf-8', errors='replace')


def read_bytes(data: bytes, offset: int, length: int) -> bytes:
    """Read a fixed-length byte sequence from data at offset."""
    return data[offset:offset+length]


def write_u8(value: int) -> bytes:
    """Convert an unsigned 8-bit integer to bytes."""
    if not 0 <= value <= 0xFF:
        raise ValueError(f"Value {value} out of range for uint8")
    return U8.pack(value)


def write_u16(value: int) -> bytes:
    """Convert an unsigned 16-bit integer to bytes."""
    if not 0 <= value <= 0xFFFF:
        raise ValueError(f"Value {value} out of range for uint16")
    return U16.pack(value)


def write_u32(value: int) -> bytes:
    """Convert an unsigned 32-bit integer to bytes."""
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError(f"Value {value} out of range for uint32")
    return U32.pack(value)


def write_s8(value: int) -> bytes:
    """Convert a signed 8-bit integer to bytes."""
    if not -0x80 <= value <= 0x7F:
        raise ValueError(f"Value {value} out of range for int8")
    return S8.pack(value)


def write_s16(value: int) -> bytes:
    """Convert a signed 16-bit integer to bytes."""
    if not -0x8000 <= value <= 0x7FFF:
        raise ValueError(f"Value {value} out of range for int16")
    return S16.pack(value)


def write_s32(value: int) -> bytes:
    """Convert a signed 32-bit integer to bytes."""
    if not -0x80000000 <= value <= 0x7FFFFFFF:
        raise ValueError(f"Value {value} out of range for int32")
    return S32.pack(value)


def write_float(value: float) -> bytes:
    """Convert a 32-bit float to bytes."""
    return FLOAT.pack(value)


def write_string(value: str, fixed_length: Optional[int] = None) -> bytes:
    """Convert a string to null-terminated UTF-8 bytes.
    
    Args:
        value: String to convert
        fixed_length: If provided, pad or truncate to this exact length
        
    Returns:
        Bytes representation of the string
    """
    encoded = value.encode('utf-8') + b'\x00'
    
    if fixed_length is not None:
        if len(encoded) > fixed_length:
            # Truncate and ensure null termination
            return encoded[:fixed_length-1] + b'\x00'
        elif len(encoded) < fixed_length:
            # Pad with zeros
            return encoded + b'\x00' * (fixed_length - len(encoded))
    
    return encoded


def pad_to_block_size(data: bytes, block_size: int = 16) -> bytes:
    """Pad data to a multiple of block_size bytes.
    
    Uses space character (0x20) as padding byte to match Miele API behavior.
    
    Args:
        data: Data to pad
        block_size: Block size to pad to (default: 16 for AES)
        
    Returns:
        Padded data
    """
    padding_needed = block_size - (len(data) % block_size)
    if padding_needed == block_size:
        return data
    
    return data + (b' ' * padding_needed)


def unpad(data: bytes) -> bytes:
    """Remove padding from data.
    
    Assumes space character (0x20) padding.
    
    Args:
        data: Padded data
        
    Returns:
        Unpadded data
    """
    # Find the first space character from the end
    i = len(data) - 1
    while i >= 0 and data[i] == 0x20:
        i -= 1
        
    return data[:i+1] 