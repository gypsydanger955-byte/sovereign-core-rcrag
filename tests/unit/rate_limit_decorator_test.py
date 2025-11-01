import asyncio
import time

import pytest

from src.rcrag.infrastructure.historian.rate_limit_decorator import RateLimitExceeded, RateLimitHistorianDecorator


class Dummy:
    def __init__(self):
        self.count = 0

    async def do(self, x: int) -> int:
        self.count += 1
        await asyncio.sleep(0)  # yield
        return x * 2


@pytest.mark.asyncio
async def test_requests_within_limit_succeed():
    d = Dummy()
    rl = RateLimitHistorianDecorator(d, rate_per_second=100, burst_size=5)
    assert await rl.do(2) == 4
    assert await rl.do(3) == 6
    assert d.count == 2


@pytest.mark.asyncio
async def test_requests_exceeding_limit_raise():
    d = Dummy()
    rl = RateLimitHistorianDecorator(d, rate_per_second=1, burst_size=1)
    # First should pass
    _ = await rl.do(1)
    # Second immediate should fail
    with pytest.raises(RateLimitExceeded):
        await rl.do(2)


@pytest.mark.asyncio
async def test_burst_capacity():
    d = Dummy()
    rl = RateLimitHistorianDecorator(d, rate_per_second=10, burst_size=3)
    # Consume burst
    await rl.do(1)
    await rl.do(2)
    await rl.do(3)
    # Next should fail without waiting
    with pytest.raises(RateLimitExceeded):
        await rl.do(4)


@pytest.mark.asyncio
async def test_token_bucket_refill_over_time():
    d = Dummy()
    rl = RateLimitHistorianDecorator(d, rate_per_second=2, burst_size=1)
    await rl.do(1)  # consume
    with pytest.raises(RateLimitExceeded):
        await rl.do(2)
    # Wait enough for at least one token
    await asyncio.sleep(0.6)
    assert await rl.do(3) == 6
