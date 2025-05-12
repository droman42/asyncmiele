import pytest
from unittest.mock import AsyncMock

from asyncmiele import MieleClient
from asyncmiele.dop2.models import SFValue


@pytest.fixture
def client():
    return MieleClient(
        host="192.168.1.50",
        group_id=bytes.fromhex("0123456789abcdef"),
        group_key=bytes.fromhex("0123456789abcdef" * 8),
    )


@pytest.mark.asyncio
async def test_get_setting(client):
    sf = SFValue(sf_id=100, current_value=10, minimum=0, maximum=20, default=5)
    client.dop2_get_parsed = AsyncMock(return_value=sf)

    result = await client.get_setting("0001", 100)
    assert result is sf


@pytest.mark.asyncio
async def test_set_setting_validation(client):
    sf = SFValue(sf_id=100, current_value=10, minimum=0, maximum=20, default=5)
    client.dop2_get_parsed = AsyncMock(return_value=sf)
    client.dop2_write_leaf = AsyncMock(return_value=None)

    # invalid
    with pytest.raises(ValueError):
        await client.set_setting("0001", 100, 30)

    # valid
    await client.set_setting("0001", 100, 15)
    client.dop2_write_leaf.assert_awaited() 