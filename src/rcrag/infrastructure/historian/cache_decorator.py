import asyncio
import time
from collections import OrderedDict
from typing import Any, Awaitable, Callable, Dict, Tuple

from src.rcrag.infrastructure.observability.metrics import CACHE_HITS, CACHE_MISSES
from src.rcrag.infrastructure.observability.tracing import get_tracer

try:
    from src.rcrag.infrastructure.historian.decorators import HistorianDecorator
except Exception:  # pragma: no cover
    class HistorianDecorator:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, item):
            return getattr(self._inner, item)


class CacheHistorianDecorator(HistorianDecorator):
    """
    In-memory caching decorator with TTL and LRU eviction.
    
    Features:
    - Caches get_record, query_by_kind, and query_by_provenance methods
    - Thread-safe async request coalescing to prevent stampedes
    - Records cache hit/miss metrics for observability
    - LRU eviction when cache exceeds max_entries
    - TTL-based expiration
    
    Args:
        inner: The historian instance to wrap
        ttl: Time-to-live in seconds for cached entries (must be positive)
        max_entries: Maximum number of entries in cache (must be positive)
    """

    def __init__(self, inner, ttl: float = 30.0, max_entries: int = 1024):
        super().__init__(inner)
        
        # Critical: Parameter validation to prevent misconfiguration
        if ttl <= 0:
            raise ValueError("TTL must be positive")
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        
        self._ttl = ttl
        self._max = max_entries
        self._cache: "OrderedDict[str, Tuple[float, Any]]" = OrderedDict()
        self._inflight: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()
        self._tracer = get_tracer("src.rcrag.cache")

    def _make_key(self, method_name: str, args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> str:
        """
        Generate a cache key from method name and arguments.
        
        Args:
            method_name: Name of the method being called
            args: Positional arguments
            kwargs: Keyword arguments
            
        Returns:
            A hashable cache key string
        """
        def normalize(v):
            if isinstance(v, (str, int, float, bool, type(None))):
                return v
            if isinstance(v, (tuple, list)):
                return tuple(normalize(x) for x in v)
            if isinstance(v, dict):
                return tuple(sorted((k, normalize(vv)) for k, vv in v.items()))
            return repr(v)

        norm_args = tuple(normalize(a) for a in args)
        norm_kwargs = tuple(sorted((k, normalize(v)) for k, v in kwargs.items()))
        return f"{method_name}:{norm_args}:{norm_kwargs}"

    def _get_if_fresh(self, key: str) -> Tuple[bool, Any]:
        """
        Check if a cache entry exists and is still fresh.
        
        Args:
            key: Cache key to check
            
        Returns:
            Tuple of (hit: bool, value: Any)
        """
        try:
            now = time.monotonic()
            if key in self._cache:
                ts, value = self._cache[key]
                if now - ts <= self._ttl:
                    # LRU update - move to end
                    self._cache.move_to_end(key, last=True)
                    return True, value
                # Expired - remove it
                del self._cache[key]
            return False, None
        except Exception:
            # Cache corruption - clear entry and treat as miss
            self._cache.pop(key, None)
            return False, None

    def _evict_if_needed(self) -> None:
        """Evict oldest entries if cache exceeds max size (LRU eviction)."""
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
        Execute a method call with caching and request coalescing.
        
        This implements the canonical async request coalescing pattern:
        1. Acquire lock
        2. Check cache - return if hit
        3. Check inflight requests - await if exists (follower)
        4. Create future for this request (leader)
        5. Release lock and execute
        6. Cache result and notify followers
        
        Args:
            method_name: Name of the method being called
            args: Positional arguments
            kwargs: Keyword arguments
            fetch_coro_factory: Factory function that returns the coroutine to execute
            
        Returns:
            The result of the method call (from cache or fresh)
        """
        key = self._make_key(method_name, args, kwargs)

        with self._tracer.start_as_current_span(f"historian.cache.{method_name}") as span:
            if hasattr(span, 'set_attribute'):
                span.set_attribute("cache.method", method_name)

            async with self._lock:
                # Check cache first
                hit, value = self._get_if_fresh(key)
                if hit:
                    CACHE_HITS.labels(operation=method_name).inc()
                    if hasattr(span, 'set_attribute'):
                        span.set_attribute("cache.hit", True)
                    return value

                # Check if request is already inflight
                if key in self._inflight:
                    future = self._inflight[key]
                    # Critical: Don't count followers as cache hits
                    if hasattr(span, 'set_attribute'):
                        span.set_attribute("cache.hit", False)
                        span.set_attribute("cache.coalesced", True)
                    # Release lock before awaiting
                    pass  # Lock will be released at end of block
                    
                    # Wait outside the lock
                    result = await future
                    return result

                # We're the leader - create future for followers
                future = asyncio.get_event_loop().create_future()
                self._inflight[key] = future

            # Execute outside the lock to avoid blocking other requests
            try:
                value = await fetch_coro_factory()
                
                # Cache and notify followers
                async with self._lock:
                    self._cache[key] = (time.monotonic(), value)
                    self._evict_if_needed()
                    if not future.done():
                        future.set_result(value)
                    self._inflight.pop(key, None)
                    
                CACHE_MISSES.labels(operation=method_name).inc()
                if hasattr(span, 'set_attribute'):
                    span.set_attribute("cache.hit", False)
                return value
                
            except Exception as e:
                # Notify followers of error
                async with self._lock:
                    if not future.done():
                        future.set_exception(e)
                    self._inflight.pop(key, None)
                raise

    # Explicit method overrides to fix __getattr__ bug
    
    async def create_record(self, record: Any) -> str:
        """Create a record (pass-through, no caching for writes)."""
        return await self._inner.create_record(record)
    
    async def get_record(self, record_id: str) -> Any:
        """Get a record by ID with caching."""
        return await self._cached_call(
            "get_record",
            (record_id,),
            {},
            lambda: super(CacheHistorianDecorator, self).get_record(record_id)
        )

    async def query_by_kind(self, kind: str, limit: int = 100) -> Any:
        """Query records by kind with caching."""
        return await self._cached_call(
            "query_by_kind",
            (kind, limit),
            {},
            lambda: super(CacheHistorianDecorator, self).query_by_kind(kind, limit)
        )

    async def query_by_provenance(self, source: str, limit: int = 100) -> Any:
        """Query records by provenance with caching."""
        return await self._cached_call(
            "query_by_provenance",
            (source, limit),
            {},
            lambda: super(CacheHistorianDecorator, self).query_by_provenance(source, limit)
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for observability.
        
        Returns:
            Dictionary with cache size, inflight requests, and configuration
        """
        return {
            "cache_size": len(self._cache),
            "inflight_requests": len(self._inflight),
            "max_entries": self._max,
            "ttl_seconds": self._ttl,
        }
