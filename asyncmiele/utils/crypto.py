"""
Cryptographic utilities for Miele API communication.
"""

import hmac
import hashlib
import binascii
from typing import Tuple, Union, Dict, Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from asyncmiele.exceptions.api import DecryptionError


def create_signature(
    host: str,
    resource: str,
    date: str,
    group_key: bytes
) -> hmac.HMAC:
    """
    Create an HMAC signature for Miele API authentication.
    
    Args:
        host: Host address
        resource: API resource path
        date: Formatted date string
        group_key: Authentication group key
        
    Returns:
        HMAC object containing the signature
    """
    signature_str = f'GET\n{host}{resource}\n\napplication/vnd.miele.v1+json\n{date}\n'
    return hmac.new(
        group_key,
        bytearray(signature_str.encode('ASCII')),
        hashlib.sha256
    )


def decrypt_response(
    response_body: bytes,
    signature: bytes,
    group_key: bytes
) -> bytes:
    """
    Decrypt the API response using AES-CBC.
    
    Args:
        response_body: Encrypted response body
        signature: Signature from X-Signature header
        group_key: Authentication group key
        
    Returns:
        Decrypted response bytes
        
    Raises:
        DecryptionError: If decryption fails
    """
    try:
        key = group_key[:int(len(group_key)/2)]
        iv = signature[:int(len(signature)/2)]
        
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=default_backend()
        )
        
        decryptor = cipher.decryptor()
        return decryptor.update(response_body) + decryptor.finalize()
    except Exception as e:
        raise DecryptionError(f"Failed to decrypt response: {str(e)}")
        
        
def generate_credentials() -> Tuple[str, str]:
    """
    Generate random GroupID and GroupKey credentials for device registration.
    
    Returns:
        Tuple of (group_id, group_key) as hex strings
    """
    import random
    group_id = '%016x' % random.randrange(16**16)
    group_key = '%0128x' % random.randrange(16**128)
    return group_id, group_key 