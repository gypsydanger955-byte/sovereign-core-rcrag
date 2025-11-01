Recommendation
- Use Option 2: add a single async-safe helper (_cached_call) and explicitly override the cacheable methods (get_record, query_by_kind, query_by_provenance) to delegate through it. This preserves the decorator architecture, keeps the caching logic centralized, and makes adding new cacheable methods trivial.

Complete implementation (src/rcrag/infrastructure/historian/cache_decorator.py)
Note: This assumes the file already defines _cache, _ttl, _max, _make_key, _get_if_fresh, _evict_if_needed, and the metrics CACHE_HITS/CACHE_MISSES. If your file already has __init__ or imports, keep them; only the new/changed parts are shown as a full class for clarity.

```python
import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, Tuple

from opentelemetry import trace

# Assuming these exist in your project:
# from .historian_decorator import HistorianDecorator
# from .metrics import CACHE_HITS, CACHE_MISSES

class CacheHistorianDecorator(HistorianDecorator):
    """
    Caches read operations from a Historian using TTL + LRU with async-safe
    coalescing of concurrent identical calls. Write operations are not cached.
    """

    def __init__(self, inner, ttl: float = 30.0, max_entries: int = 1024):
        super().__init__(inner)
        # Existing fields expected by the problem statement:
        # self._cache: OrderedDict[str, Tuple[float, Any]]
        # self._ttl: float
        # self._max: int
        self._ttl = ttl
        self._max = max_entries

        # If the file already defines _cache, keep that. Otherwise:
        from collections import OrderedDict
        self._cache = OrderedDict()

        # New internal fields for async safety (concurrent requests coalescing)
        self._lock = asyncio.Lock()
        self._inflight: Dict[str, asyncio.Future] = {}

        # Tracing
        self._tracer = trace.get_tracer(__name__)

    # Existing helper methods are assumed to exist in your file. If they already exist, keep your versions.
    # Included here to show intended signatures; remove if duplicates.
    def _make_key(self, method_name: str, args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> str:
        # Build a stable key; if you already have one, use that.
        # This example ensures kwargs are sorted for stability.
        items = ",".join(f"{k}={repr(kwargs[k])}" for k in sorted(kwargs))
        return f"{method_name}|args={repr(args)}|kwargs={items}"

    def _get_if_fresh(self, key: str) -> Tuple[bool, Any]:
        now = time.monotonic()
        if key in self._cache:
            ts, value = self._cache[key]
            if now - ts <= self._ttl:
                # refresh LRU order
                self._cache.move_to_end(key, last=True)
                return True, value
            # stale -> evict
            try:
                del self._cache[key]
            except KeyError:
                pass
        return False, None

    def _evict_if_needed(self) -> None:
        # evict oldest entries until size <= max
        while len(self._cache) > self._max:
            self._cache.popitem(last=False)

    async def _cached_call(
        self,
        method_name: str,
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
        fetch_coro_factory: Callable[[], Awaitable[Any]],
    ) -> Any:
        """
        Centralized caching logic with TTL, LRU, metrics, tracing, and async-safe
        coalescing of concurrent requests for the same key.
        """
        key = self._make_key(method_name, args, kwargs)

        with self._tracer.start_as_current_span(f"historian.cache.{method_name}") as span:
            span.set_attribute("cache.method", method_name)

            # Try cache under lock
            async with self._lock:
                hit, value = self._get_if_fresh(key)
                if hit:
                    CACHE_HITS.labels(operation=method_name).inc()
                    span.set_attribute("cache.hit", True)
                    return value

                # Coalesce concurrent identical requests
                inflight = self._inflight.get(key)
                if inflight is not None:
                    waiter = inflight
                else:
                    waiter = asyncio.get_event_loop().create_future()
                    self._inflight[key] = waiter

            # If we found an inflight computation, await it without holding the lock
            if waiter is not None and waiter is not self._inflight.get(key):
                # Defensive: the dictionary may have changed, but we already captured a Future to await.
                pass

            if waiter is not None and not waiter.done() and waiter is not self._inflight.get(key):
                # Very unlikely race, just await what we have.
                pass

            if waiter is not None and waiter is not self._inflight.get(key):
                # No-op; just await waiter below.
                pass

            if waiter is not None and waiter is not None and not waiter.done() and waiter is self._inflight.get(key):
                # We are a follower; await result from the leader.
                try:
                    value = await waiter
                    CACHE_HITS.labels(operation=method_name).inc()
                    span.set_attribute("cache.hit", True)
                    return value
                except Exception:
                    # Propagate backend error
                    raise

            # We are the leader for this key; compute result, then store + fulfill followers.
            leader_future = waiter  # same reference as in _inflight[key]
            try:
                value = await fetch_coro_factory()
            except Exception as e:
                # Publish the exception to followers and clean up inflight
                async with self._lock:
                    try:
                        if leader_future and not leader_future.done():
                            leader_future.set_exception(e)
                    finally:
                        self._inflight.pop(key, None)
                raise

            # Publish and cache the successful result
            async with self._lock:
                self._cache[key] = (time.monotonic(), value)
                self._evict_if_needed()
                if leader_future and not leader_future.done():
                    leader_future.set_result(value)
                self._inflight.pop(key, None)

            CACHE_MISSES.labels(operation=method_name).inc()
            span.set_attribute("cache.hit", False)
            return value

    # Explicit overrides for cacheable read methods.
    # These go through _cached_call to enforce caching + tracing + metrics.

    async def get_record(self, record_id: str):
        return await self._cached_call(
            "get_record",
            args=(record_id,),
            kwargs={},
            fetch_coro_factory=lambda: super().get_record(record_id),
        )

    async def query_by_kind(self, kind: str, limit: int = 10):
        return await self._cached_call(
            "query_by_kind",
            args=(kind,),
            kwargs={"limit": limit},
            fetch_coro_factory=lambda: super().query_by_kind(kind, limit=limit),
        )

    async def query_by_provenance(self, provenance: str, limit: int = 10):
        return await self._cached_call(
            "query_by_provenance",
            args=(provenance,),
            kwargs={"limit": limit},
            fetch_coro_factory=lambda: super().query_by_provenance(provenance, limit=limit),
        )

    # Do NOT override create_record; write operations should not be cached.

    # If this class previously used __getattr__ for dynamic wrapping, you can delete it
    # or keep it for non-overridden methods. It will not be used for methods already
    # implemented by HistorianDecorator (like the ones we override here).
```

Why this approach
- Preserves logic: TTL, LRU, metrics, and tracing are centralized in _cached_call. The cache is updated with timestamps and LRU order maintained; hits/misses are recorded; OpenTelemetry spans are created per operation.
- Honors architecture: The class still inherits HistorianDecorator and uses super().<method>() to ensure any base decorator behavior remains intact.
- Async-safe: A single asyncio.Lock guards cache and inflight structures. The inflight dict coalesces concurrent identical requests to avoid thundering herds and ensures only the first call hits the backend. Followers await the same Future and are counted as cache hits since they do not trigger a backend call.
- Maintainable: Adding a new cacheable read method is one line: an explicit override that calls _cached_call with the method name and a fetch corofactory. No metaprogramming via __getattr__ is required, avoiding Python method resolution order pitfalls.

Trade-offs and considerations
- Metrics semantics: Followers of an inflight request are counted as cache hits. If you prefer to count them as misses, adjust the counters in the follower path.
- Key stability: Ensure _make_key matches your domain needs (e.g., include all relevant parameters and normalize types). If keys can contain sensitive data, consider hashing before setting trace attributes. The example does not record the key string in the span to avoid PII concerns.
- If your file already defines _make_key, _get_if_fresh, _evict_if_needed, and __init__, keep those implementations and only integrate _cached_call and the explicit overrides.