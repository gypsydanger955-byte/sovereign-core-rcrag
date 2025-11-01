```python
import asyncio
from collections import OrderedDict
from typing import Any, Callable, Dict, Tuple

from opentelemetry import trace

# Presumed these are imported from elsewhere in your codebase:
from prometheus_client import Counter
from src.rcrag.domain.ports.historian import HistorianPort
from src.rcrag.infrastructure.historian.decorator import HistorianDecorator


CACHE_HITS = Counter("historian_cache_hits", "Cache hits in historian decorator", ["operation"])
CACHE_MISSES = Counter("historian_cache_misses", "Cache misses in historian decorator", ["operation"])

tracer = trace.get_tracer(__name__)


class CacheHistorianDecorator(HistorianDecorator):
    def __init__(self, inner: HistorianPort, ttl: float = 300, max_size: int = 1024):
        super().__init__(inner)
        self._cache: "OrderedDict[str, Tuple[float, Any]]" = OrderedDict()  # key -> (timestamp, value)
        self._ttl = ttl
        self._max = max_size
        self._lock = asyncio.Lock()

    def _make_key(self, method_name: str, args: Tuple, kwargs: Dict) -> str:
        # Simplistic key generation; can be improved as needed.
        key = f"{method_name}:{args}:{sorted(kwargs.items())}"
        return key

    def _get_if_fresh(self, key: str) -> Tuple[bool, Any]:
        """
        Check if cache has fresh entry for key.
        Returns (hit: bool, value: Any)
        """
        entry = self._cache.get(key)
        if entry is None:
            return False, None
        timestamp, value = entry
        if (trace.get_time_ns() / 1e9) - timestamp > self._ttl:
            # Expired
            self._cache.pop(key, None)
            return False, None
        return True, value

    def _evict_if_needed(self) -> None:
        while len(self._cache) > self._max:
            self._cache.popitem(last=False)  # pop oldest item (LRU)

    async def _cached_call(self, method_name: str, *args, **kwargs) -> Any:
        key = self._make_key(method_name, args, kwargs)

        async with self._lock:
            hit, value = self._get_if_fresh(key)
            if hit:
                CACHE_HITS.labels(operation=method_name).inc()
                # Move this key to the end to mark as recently used
                self._cache.move_to_end(key)
                return value

        # Cache miss - fetch under lock cleared to allow concurrency for fetch
        with tracer.start_as_current_span(f"CacheHitMiss/{method_name}"):
            value = await getattr(self._inner, method_name)(*args, **kwargs)

        async with self._lock:
            CACHE_MISSES.labels(operation=method_name).inc()
            now = trace.get_time_ns() / 1e9
            self._cache[key] = (now, value)
            self._evict_if_needed()

        return value

    # === Cached methods ===
    async def get_record(self, record_id: str):
        """
        Cache this read method.
        """
        return await self._cached_call("get_record", record_id)

    async def query_by_kind(self, kind: str, limit: int = 10):
        """
        Cache this read method.
        """
        return await self._cached_call("query_by_kind", kind, limit=limit)

    async def query_by_provenance(self, provenance: str, limit: int = 10):
        """
        Cache this read method.
        """
        return await self._cached_call("query_by_provenance", provenance, limit=limit)

    # === Non-cached methods ===
    # Just delegate directly, do not cache write methods:
    async def create_record(self, *args, **kwargs):
        return await self._inner.create_record(*args, **kwargs)
```

---

# Explanation

## Recommended Approach: Option 2 with Explicit Method Overrides

I implemented **Option 2**, which uses a helper method `_cached_call` that contains the shared caching logic and tracing/metrics integration. Then, the cacheable methods (`get_record`, `query_by_kind`, `query_by_provenance`) explicitly override the base class methods to call `_cached_call`.

### Why this is best:

- **Explicit overrides avoid `__getattr__` pitfalls:** Since the base class `HistorianDecorator` defines the same method names, `__getattr__` is never called. Explicit overrides ensure our caching logic is applied.

- **Centralized caching logic:** The `_cached_call` method implements caching, locking, TTL checks, eviction, metrics, and tracing in one place, avoiding duplication.

- **Maintainable and easy to extend:** To cache a new method, simply add an override that calls `_cached_call`.

- **Async concurrency safe:** Uses an asyncio lock to serialize cache access and updates to avoid race conditions.

- **Counts hits and misses:** Using Prometheus metrics, with precise labels.

- **OpenTelemetry tracing:** Wraps the actual backend call in a span named `CacheHitMiss/<method>`, so you can monitor cache performance easily.

- **Write operations excluded from cache:** `create_record` and any other non-cacheable methods directly delegate to the inner historian without any caching or locking.

---

# Trade-offs and Considerations:

- **Locking granularity:** The current `_lock` serializes all cache access. For very high concurrency, a per-key lock might reduce contention but adds complexity.

- **Key generation:** `_make_key` uses a simple stringification of method arguments. This should be adequate but can be improved or replaced with a serialization mechanism for robustness.

- **Cache size & TTL tuning:** `_max` and `_ttl` are constructor-configurable; choose sensible defaults according to workload.

- **Cache invalidation:** This design does not automatically invalidate caches on writes — e.g., if a record is created or updated, the cache may be stale. Consider adding explicit invalidation hooks if needed.

- **Error handling:** Exceptions from underlying calls are propagated without caching. This is typical behavior but can be changed as needed.

- **Metrics and tracing require proper setup elsewhere** in your application.

---

This approach cleanly fixes the original bug (no caching due to `__getattr__` not triggering) while preserving all existing functionality and infrastructure, meeting all your constraints with maintainable, clear code.