import asyncio
from unittest.mock import AsyncMock

import pytest

from asyncmiele import MieleClient
from asyncmiele.dop2.models import ConsumptionStats, TariffConfig


@pytest.fixture
def client():
    return MieleClient(
        host="192.168.1.50",
        group_id=bytes.fromhex("0123456789abcdef"),
        group_key=bytes.fromhex("0123456789abcdef" * 8),
    )


@pytest.mark.asyncio
async def test_consumption_stats_basic(client):
    async def fake_parsed(device_id: str, unit: int, attribute: int, *, idx1: int = 0, idx2: int = 0):
        if (unit, attribute) == (2, 119):
            return 100  # hours
        if (unit, attribute) == (2, 138):
            return 25   # cycles
        if (unit, attribute) == (2, 6195):
            return {"energy_wh_total": 123456, "water_l_total": 789}
        raise ValueError("Unexpected leaf")

    client.dop2_get_parsed = AsyncMock(side_effect=fake_parsed)

    stats = await client.get_consumption_stats("0001")
    assert isinstance(stats, ConsumptionStats)
    assert stats.hours_of_operation == 100
    assert stats.cycles_completed == 25
    assert stats.energy_wh_total == 123456
    assert stats.water_l_total == 789


@pytest.mark.asyncio
async def test_cost_estimation():
    stats = ConsumptionStats(
        hours_of_operation=10,
        cycles_completed=5,
        energy_wh_total=1500,  # 1.5 kWh
        water_l_total=50,
    )

    tariff = TariffConfig(energy_price_per_kwh=0.30, water_price_per_litre=0.004)
    cost = stats.estimate_total_cost(tariff)
    # Expected: 1.5 * 0.30 + 50 * 0.004 = 0.45 + 0.2 = 0.65
    assert cost == pytest.approx(0.65) 