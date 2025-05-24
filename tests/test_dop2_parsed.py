import asyncio
import pytest
from unittest.mock import AsyncMock

from asyncmiele import MieleClient
from asyncmiele.dop2.models import DeviceCombinedState, SFValue


@pytest.fixture
def client():
    c = MieleClient(
        host="192.168.1.50",
        group_id=bytes.fromhex("0123456789abcdef"),
        group_key=bytes.fromhex("0123456789abcdef" * 8),
    )
    return c


@pytest.mark.asyncio
async def test_parsed_device_state(client):
    # build fake payload 3x u16: 0, 1, 2
    payload = bytes([0, 0, 0, 1, 0, 2])
    client.read_dop2_leaf = AsyncMock(return_value=payload)

    parsed = await client.get_parsed_dop2_leaf("0001", 2, 256)
    assert isinstance(parsed, DeviceCombinedState)
    assert parsed.appliance_state == 0
    assert parsed.operation_state == 1
    assert parsed.process_state == 2


@pytest.mark.asyncio
async def test_parsed_sf_value(client):
    # sf_id=100, current=10, min=0, max=20, default=5
    payload = bytes([0, 100, 0, 10, 0, 0, 0, 20, 0, 5])
    client.read_dop2_leaf = AsyncMock(return_value=payload)

    parsed = await client.get_parsed_dop2_leaf("0001", 2, 105)
    assert isinstance(parsed, SFValue)
    assert parsed.sf_id == 100
    assert parsed.current_value == 10
    assert parsed.range == (0, 20) 