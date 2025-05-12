import hashlib
import hmac

from asyncmiele.utils.crypto import build_auth_header


def test_build_auth_header_get():
    host = "192.168.1.50"
    resource = "/Devices/"
    date = "Thu, 01 Jan 1970 00:00:00 GMT"
    group_id_hex = "0123456789abcdef"
    group_key_hex = "00112233445566778899aabbccddeeff" * 4  # 64 bytes / 128 hex chars

    group_id = bytes.fromhex(group_id_hex)
    group_key = bytes.fromhex(group_key_hex)

    auth_header, iv = build_auth_header(
        method="GET",
        host=host,
        resource=resource,
        date=date,
        group_id=group_id,
        group_key=group_key,
    )

    # --- expected values ----------------------------------------------------
    canonical = (
        f"GET\n{host}{resource}\n\napplication/vnd.miele.v1+json\n{date}\n".encode(
            "ASCII"
        )
    )
    expected_digest = hmac.new(group_key, canonical, hashlib.sha256).hexdigest().upper()
    expected_header = f"MieleH256 {group_id_hex}:{expected_digest}"

    assert auth_header == expected_header
    assert len(iv) == 16
    # IV must be first 16 bytes of digest
    assert iv == bytes.fromhex(expected_digest)[:16] 