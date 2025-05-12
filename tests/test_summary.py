import pytest
from unittest.mock import AsyncMock

from asyncmiele import MieleClient
from asyncmiele.models.summary import DeviceSummary
from asyncmiele.dop2.models import DeviceCombinedState
from asyncmiele.models.device import DeviceIdentification, DeviceState


@pytest.fixture
def client():
    c = MieleClient(
        host="192.168.1.50",
        group_id=bytes.fromhex("0123456789abcdef"),
        group_key=bytes.fromhex("0123456789abcdef" * 8),
    )
    return c


@pytest.mark.asyncio
async def test_get_summary(client):
    client.get_device_ident = AsyncMock(return_value=DeviceIdentification(device_name="Washer"))
    client.get_device_state = AsyncMock(return_value=DeviceState(remaining_time=300, elapsed_time=600))
    client.dop2_get_parsed = AsyncMock(return_value=DeviceCombinedState(0, 0, 0))
    client.can_remote_start = AsyncMock(return_value=True)

    summary = await client.get_summary("0001")
    assert isinstance(summary, DeviceSummary)
    assert summary.name == "Washer"
    assert summary.progress == 600 / 900
    assert summary.ready_to_start is True 