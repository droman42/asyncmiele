"""
Cryptographic utilities for Miele API communication.
"""

import hmac
import hashlib
import binascii
from typing import Tuple, Dict, Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from asyncmiele.exceptions.api import DecryptionError


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

# New generic helper ----------------------------------------------------------

def _hmac_signature(payload: bytes, key: bytes) -> str:
    """Return upper-case hex SHA-256 HMAC for *payload* using *key*."""
    mac = hmac.new(key, payload, hashlib.sha256)
    return mac.hexdigest().upper()


def build_auth_header(
    method: str,
    host: str,
    resource: str,
    date: str,
    group_id: bytes,
    group_key: bytes,
    *,
    accept_header: str = "application/vnd.miele.v1+json",
    content_type_header: str = "",
    body: bytes | str | None = None,
) -> tuple[str, bytes]:
    """Generate `Authorization` header and IV for Miele local API.

    Parameters
    ----------
    method
        HTTP verb (e.g. "GET", "PUT").
    host
        Host part without schema (e.g. "192.168.1.50").
    resource
        Absolute path starting with `/`, *without* host.
    date
        RFC-1123 date string – must match the `Date` request header.
    group_id, group_key
        Credentials obtained during commissioning.
    accept_header
        Accept header value (default matches v1 JSON).
    content_type_header
        Content-Type header value; empty for GET.
    body
        Raw request body **before encryption/padding**.  Leave ``None`` for GET.

    Returns
    -------
    tuple
        ``(authorization_header, iv_bytes)`` where the header is ready to put
        into the request and *iv_bytes* is the first 16 bytes of the SHA-256
        HMAC (needed to encrypt the body for PUT).
    """
    method = method.upper()

    if body is None:
        body_bytes: bytes = b""
    elif isinstance(body, str):
        body_bytes = body.encode("utf-8")
    else:
        body_bytes = body

    # Construct the canonical payload string exactly matching MieleRESTServer
    # MieleRESTServer: payload=f"{httpMethod}\n{host}/{resourcePath}\n{contentTypeHeader}\n{acceptHeader}\n{date}\n";
    # resourcePath is used without leading slash, so we need to strip it
    resource_path = resource.lstrip('/')
    canonical = (
        f"{method}\n{host}/{resource_path}\n{content_type_header}\n{accept_header}\n{date}\n".encode(
            "utf-8"
        )
        + body_bytes
    )

    digest_hex = _hmac_signature(canonical, group_key)

    # The IV is the first 16 *bytes* of the hash, not the first 16 hex chars.
    iv_bytes = bytes.fromhex(digest_hex)[:16]

    # FIXED: Use uppercase GroupID to match MieleRESTServer behavior
    # MieleRESTServer uses: self.provisioningInfo.groupid (which is .upper())
    auth_header = f"MieleH256 {group_id.hex().upper()}:{digest_hex}"
    return auth_header, iv_bytes

def pad_payload(payload: bytes, blocksize: int = 16) -> bytes:
    """Pad payload with ASCII space (0x20) to match MieleRESTServer behavior exactly.
    
    MieleRESTServer padding logic:
    - For JSON strings: payload[0:-1] + " "* (64-len(payload)) + "}"
    - For binary: payload.ljust(len(payload) + padding, b'\x20')
    
    Args:
        payload: The payload to pad
        blocksize: Block size for padding (default 16 for AES)
        
    Returns:
        Padded payload
    """
    if len(payload) == 0:
        return payload
        
    # Check if this looks like a JSON payload (common case)
    try:
        payload_str = payload.decode('utf-8')
        if payload_str.strip().startswith('{') and payload_str.strip().endswith('}'):
            # FIXED: Use exact MieleRESTServer JSON padding logic
            # MieleRESTServer: payload=payload[0:-1] + " "* (64-len(payload)) + "}";
            if payload_str[-1] != "}":
                raise Exception("Plaintext must be terminated with literal '}'")
            
            if len(payload_str) >= 64:
                # For larger payloads, no special padding needed
                return payload
            else:
                # For smaller JSON, pad to 64 bytes by inserting spaces before }
                spaces_needed = 64 - len(payload_str)
                if spaces_needed > 0:
                    padded_str = payload_str[0:-1] + " " * spaces_needed + "}"
                    return padded_str.encode('utf-8')
                else:
                    return payload
    except UnicodeDecodeError:
        # Not UTF-8, treat as binary
        pass
    
    # FIXED: Use exact MieleRESTServer binary padding logic
    # MieleRESTServer: payload.ljust(len(payload) + padding, b'\x20')
    if len(payload) % blocksize == 0:
        return payload
    padding = blocksize - (len(payload) % blocksize)
    return payload.ljust(len(payload) + padding, b'\x20')


def encrypt_payload(plaintext: bytes, key: bytes, iv: bytes) -> bytes:
    """AES-CBC encrypt *plaintext* using the same scheme as Miele devices."""
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    return encryptor.update(plaintext) + encryptor.finalize() 

# ---------------------------------------------------------------------------
# Decryption helpers (Phase-2 symmetry)
# ---------------------------------------------------------------------------

def decrypt_and_unpad(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    """AES-CBC decrypt *ciphertext* and strip trailing ASCII-space padding."""
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    return plaintext.rstrip(b"\x20")


def decrypt_response(
    response_body: bytes,
    signature: bytes,
    group_key: bytes,
) -> bytes:
    """Decrypt and un-pad API response using AES-CBC.

    Parameters
    ----------
    response_body
        Encrypted payload bytes.
    signature
        Hex signature from *X-Signature* header (already binascii-decoded).
    group_key
        Full 32-byte group key; encryption uses the first 16 bytes.
    """
    try:
        key = group_key[: len(group_key) // 2]
        iv = signature[: len(signature) // 2]
        return decrypt_and_unpad(response_body, key, iv)
    except Exception as e:  # pragma: no cover – defensive
        raise DecryptionError(f"Failed to decrypt response: {e}") from e 