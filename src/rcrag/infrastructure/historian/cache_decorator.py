"""Cache decorator for Historian with explicit method overrides."""

import asyncio
import time
from typing import Any, Dict, List, Optional

from src.rcrag.domain.models import HistorianRecord
from src.rcrag.domain.ports.historian_port import HistorianPort
from src.rcrag.infrastructure.observability.metrics import CACHE_HITS, CACHE_MISSES
from src.rcrag.infrastructure.observability.tracing import get_tracer

try:
    import orjson  # Fast, canonical JSON serializer
except ImportError:
    orjson = None


def canonical_serialize(obj: Any) -> str:
    """
    Serialize a Python object into a canonical JSON string with:
    - Sorted keys for dicts
    - Lists for tuples
    - Deterministic output for nested structures
    
    Falls back gracefully if serialization fails.
    """
    def convert(o):
        if isinstance(o, dict):
            # Recursively sort dict keys and convert values
            return {k: convert(o[k]) for k in sorted(o)}
        elif isinstance(o, (list, tuple)):
            # Convert tuples to lists and recursively convert elements
            return [convert(i) for i in o]
        else:
            return o
    
    try:
        canonical_obj = convert(obj)
        if orjson:
            # orjson dumps bytes, decode to str
            return orjson.dumps(canonical_obj, option=orjson.OPT_SORT_KEYS).decode('utf-8')
        else:
            import json
            return json.dumps(canonical_obj, sort_keys=True, separators=(',', ':'))
    except Exception as ex:
        # Defensive fallback: log and return safe repr string
        print(f"[CacheDecorator] Warning: serialization failed for object {obj!r}, error: {ex}")
        return repr(obj)


def make_cache_key(
    prefix: str,
    *args: Any,
    filters: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
    query: Optional[str] = None
) -> str:
    """
    Construct a stable, collision-resistant cache key string.
    
    Args:
        prefix: Query type identifier
        *args: Positional arguments
        filters: Optional filter dict
        limit: Optional result limit
        query: Optional search query string
    
    Returns:
        Canonical cache key string
    """
    parts = [prefix]
    
    # Add positional args
    for arg in args:
        parts.append(str(arg))
    
    # Add filters (canonically serialized)
    if filters:
        parts.append(f"filters={canonical_serialize(filters)}")
    
    # Add limit
    if limit is not None:
        parts.append(f"limit={limit}")
    
    # Add query
    if query:
        parts.append(f"query={query}")
    
    return ":".join(parts)


class CacheHistorianDecorator(HistorianPort):
    """
    Caching decorator for HistorianPort with explicit method overrides.
    
    Caches read operations (get_record, query_*, search) and invalidates
    cache on write operations (create_record).
    """
    
    def __init__(
        self,
        underlying: HistorianPort,
        ttl: int = 300,  # 5 minutes default
        max_entries: int = 1000
    ):
        """
        Initialize cache decorator.
        
        Args:
            underlying: The underlying Historian implementation
            ttl: Time-to-live for cache entries in seconds
            max_entries: Maximum number of cache entries
        """
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        
        self._underlying = underlying
        self._ttl = ttl
        self._max_entries = max_entries
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()
        self._inflight: Dict[str, asyncio.Event] = {}
        self._tracer = get_tracer("src.rcrag.cache")
    
    def _is_fresh(self, timestamp: float) -> bool:
        """Check if a cache entry is still fresh."""
        return (time.time() - timestamp) < self._ttl
    
    async def _get_if_fresh(self, key: str) -> Optional[Any]:
        """Get cached value if fresh, None otherwise."""
        async with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if self._is_fresh(timestamp):
                    return value
                else:
                    # Expired, remove it
                    del self._cache[key]
        return None
    
    async def _set_cache(self, key: str, value: Any) -> None:
        """Set a cache entry with current timestamp."""
        async with self._lock:
            # Simple LRU: if at capacity, remove oldest
            if len(self._cache) >= self._max_entries:
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]
            
            self._cache[key] = (value, time.time())
    
    async def _invalidate_all(self) -> None:
        """Invalidate all cache entries (called on writes)."""
        async with self._lock:
            self._cache.clear()
    
    async def _coalesce_inflight(self, key: str, method_name: str, coro):
        """
        Coalesce concurrent requests for the same key.
        
        If multiple requests for the same key arrive while one is in-flight,
        only one actually executes and others wait for its result.
        """
        async with self._lock:
            if key in self._inflight:
                # Another request is in-flight, wait for it
                event = self._inflight[key]
        
        if key in self._inflight:
            # Wait for the in-flight request to complete
            await event.wait()
            # Now the result should be in cache
            return await self._get_if_fresh(key)
        
        # We're the first, create event and execute
        async with self._lock:
            if key not in self._inflight:
                self._inflight[key] = asyncio.Event()
        
        try:
            # Execute the underlying operation
            result = await coro
            # Cache the result
            await self._set_cache(key, result)
            # Record cache miss
            CACHE_MISSES.labels(operation=method_name).inc()
            return result
        finally:
            # Signal completion and remove from inflight
            async with self._lock:
                if key in self._inflight:
                    self._inflight[key].set()
                    del self._inflight[key]
    
    # Explicit method overrides for ALL HistorianPort methods
    
    async def create_record(self, record: HistorianRecord) -> str:
        """
        Create a record (write operation - invalidates cache).
        """
        result = await self._underlying.create_record(record)
        # Invalidate cache on write
        await self._invalidate_all()
        return result
    
    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        """
        Get a record by ID (cached).
        """
        key = make_cache_key("get_record", record_id)
        
        # Check cache first
        cached = await self._get_if_fresh(key)
        if cached is not None:
            CACHE_HITS.labels(operation="get_record").inc()
            return cached
        
        # Cache miss - fetch with inflight coalescing
        async def fetch():
            return await self._underlying.get_record(record_id)
        
        return await self._coalesce_inflight(key, "get_record", fetch())
    
    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        """
        Query records by kind (cached).
        """
        key = make_cache_key("query_by_kind", kind, limit=limit)
        
        # Check cache first
        cached = await self._get_if_fresh(key)
        if cached is not None:
            CACHE_HITS.labels(operation="query_by_kind").inc()
            return cached
        
        # Cache miss - fetch with inflight coalescing
        async def fetch():
            return await self._underlying.query_by_kind(kind, limit)
        
        return await self._coalesce_inflight(key, "query_by_kind", fetch())
    
    async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]:
        """
        Query records by provenance (cached).
        """
        key = make_cache_key("query_by_provenance", source_id)
        
        # Check cache first
        cached = await self._get_if_fresh(key)
        if cached is not None:
            CACHE_HITS.labels(operation="query_by_provenance").inc()
            return cached
        
        # Cache miss - fetch with inflight coalescing
        async def fetch():
            return await self._underlying.query_by_provenance(source_id)
        
        return await self._coalesce_inflight(key, "query_by_provenance", fetch())
    
    async def search(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[HistorianRecord]:
        """
        Search records (cached).
        """
        key = make_cache_key("search", query=query, filters=filters, limit=limit)
        
        # Check cache first
        cached = await self._get_if_fresh(key)
        if cached is not None:
            CACHE_HITS.labels(operation="search").inc()
            return cached
        
        # Cache miss - fetch with inflight coalescing
        async def fetch():
            return await self._underlying.search(query, filters, limit)
        
        return await self._coalesce_inflight(key, "search", fetch())
    
    async def query_records(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[HistorianRecord]:
        """
        Query records with filters (cached).
        """
        key = make_cache_key("query_records", filters=filters, limit=limit)
        
        # Check cache first
        cached = await self._get_if_fresh(key)
        if cached is not None:
            CACHE_HITS.labels(operation="query_records").inc()
            return cached
        
        # Cache miss - fetch with inflight coalescing
        async def fetch():
            return await self._underlying.query_records(filters, limit)
        
        return await self._coalesce_inflight(key, "query_records", fetch())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._cache),
            "max_entries": self._max_entries,
            "ttl_seconds": self._ttl,
            "inflight_requests": len(self._inflight)
        }
