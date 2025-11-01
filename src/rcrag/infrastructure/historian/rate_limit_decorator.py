import asyncio
import inspect
import time
from typing import Callable

from src.rcrag.infrastructure.observability.metrics import HISTORIAN_OPERATION_DURATION, RATE_LIMIT_HITS
from src.rcrag.infrastructure.observability.tracing import get_tracer

try:
    from src.rcrag.infrastructure.historian.decorators import HistorianDecorator  # type: ignore
except Exception:  # pragma: no cover
    class HistorianDecorator:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, item):
            return getattr(self._inner, item)


class RateLimitExceeded(Exception):
    pass


class RateLimitHistorianDecorator(HistorianDecorator):
    """
    Token bucket rate limiter for historian operations.
    Applies to all async methods on the historian.
    """

    def __init__(self, inner, rate_per_second: float = 10.0, burst_size: int = 20):
        super().__init__(inner)
        if rate_per_second <= 0 or burst_size <= 0:
            raise ValueError("rate_per_second and burst_size must be > 0")
        self._rate = float(rate_per_second)
        self._capacity = float(burst_size)
        self._tokens = float(burst_size)
        self._last_refill = time.monotonic()
        self._tracer = get_tracer("src.rcrag.rate_limit")

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed <= 0:
            return
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now

    def _consume(self) -> bool:
        self._refill()
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    def __getattr__(self, name: str):
        target = getattr(self._inner, name)
        if not inspect.iscoroutinefunction(target):
            return target

        async def wrapper(*args, **kwargs):
            if not self._consume():
                RATE_LIMIT_HITS.labels(operation=name).inc()
                raise RateLimitExceeded(f"Rate limit exceeded for {name}")
            with self._tracer.start_as_current_span(f"rate_limit:{name}"):
                start = time.perf_counter()
                try:
                    return await target(*args, **kwargs)
                finally:
                    elapsed = time.perf_counter() - start
                    HISTORIAN_OPERATION_DURATION.labels(operation=name).observe(elapsed)

        return wrapper
