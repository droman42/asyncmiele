import asyncio
from unittest.mock import AsyncMock

import pytest

from asyncmiele.subscription import SubscriptionManager
from asyncmiele.models.summary import DeviceSummary
from asyncmiele import MieleClient
from asyncmiele.models.device import DeviceIdentification, DeviceState


@pytest.fixture
def client():
    return MieleClient(
        host="192.168.1.50",
        group_id=bytes.fromhex("0123456789abcdef"),
        group_key=bytes.fromhex("0123456789abcdef" * 8),
    )


@pytest.mark.asyncio
async def test_subscription_triggers_on_change(client):
    from asyncmiele.models.device import DeviceIdentification, DeviceState
    dummy_ident = DeviceIdentification()
    dummy_state = DeviceState()

    summaries = [
        DeviceSummary(id="0001", name="dev", ident=dummy_ident, state=dummy_state),
        DeviceSummary(id="0001", name="dev", ident=dummy_ident, state=dummy_state, progress=0.5),
    ]
    get_summary_mock = AsyncMock(side_effect=summaries)
    client.get_summary = get_summary_mock  # type: ignore

    events: list[DeviceSummary] = []

    async def cb(new, old):
        events.append(new)

    sub = SubscriptionManager(client, interval=0.01)
    sub.add_listener("0001", cb)

    await sub.start()
    await asyncio.sleep(0.03)  # allow two polls
    await sub.stop()

    # Should have at least one event fired (after second poll where progress changed)
    assert len(events) >= 1 