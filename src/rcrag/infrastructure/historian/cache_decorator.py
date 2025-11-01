"""
Cache decorator for Historian with pagination-aware invalidation.

Implements a two-tier cache key structure with an InvalidationRegistry to correctly
invalidate all paginated pages when data changes.

Limitations:
- Registry memory grows with query diversity; periodic cleanup recommended for long-running processes
- Search invalidation is conservative (filter-based only, not query-text aware)
- Filter order independence achieved via JSON sorting; custom object types may not normalize perfectly
- No support for complex filter predicates (OR, NOT, nested conditions)
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from src.rcrag.domain.models import HistorianRecord
from src.rcrag.domain.ports.historian_port import HistorianPort
from src.rcrag.infrastructure.observability.metrics import CACHE_HITS, CACHE_MISSES
from src.rcrag.infrastructure.observability.tracing import get_tracer


def _normalize_for_key(obj: Optional[Dict[str, Any]]) -> str:
    """
    Normalize a dict to a canonical JSON string for cache keys.
    
    Uses sorted keys and deterministic serialization to ensure
    filter order independence.
    """
    return json.dumps(obj or {}, sort_keys=True, separators=(",", ":"), default=str)


def _make_cache_keys(
    prefix: str,
    filters: Optional[Dict[str, Any]],
    limit: int,
    offset: int,
    extra: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """
    Generate two-tier cache keys for pagination-aware invalidation.
    
    Returns:
        (invalidation_key, full_cache_key)
        - inv_key excludes pagination (limit/offset)
        - full_key includes pagination
    """
    f_norm = _normalize_for_key(filters)
    e_norm = _normalize_for_key(extra)
    inv_key = f"{prefix}:f={f_norm}:x={e_norm}"
    full_key = f"{inv_key}:l={limit}:o={offset}"
    return inv_key, full_key


class InvalidationRegistry:
    """
    Tracks full cache keys per invalidation key and stores filter metadata
    for selective invalidation when records change.
    
    TODO: Add periodic cleanup mechanism to remove entries for expired cache keys.
    Registry grows unbounded as TTL expiry doesn't trigger cleanup.
    """
    
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._inv_to_full: Dict[str, Set[str]] = {}
        self._inv_meta: Dict[str, Tuple[Dict[str, Any], Dict[str, Any]]] = {}
    
    async def register(
        self,
        inv_key: str,
        full_key: str,
        filters: Optional[Dict[str, Any]],
        extra: Optional[Dict[str, Any]],
    ) -> None:
        """Register a full cache key under its invalidation key."""
        async with self._lock:
            if inv_key not in self._inv_to_full:
                self._inv_to_full[inv_key] = set()
            self._inv_to_full[inv_key].add(full_key)
            # Store raw dicts to avoid re-parsing from key strings
            self._inv_meta[inv_key] = (filters or {}, extra or {})
    
    async def keys(self) -> Set[str]:
        """Get all invalidation keys."""
        async with self._lock:
            return set(self._inv_to_full.keys())
    
    async def get_full_keys(self, inv_key: str) -> Set[str]:
        """Get all full cache keys for an invalidation key."""
        async with self._lock:
            return set(self._inv_to_full.get(inv_key, set()))
    
    async def get_meta(self, inv_key: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Get stored filter and extra metadata for an invalidation key."""
        async with self._lock:
            return self._inv_meta.get(inv_key, ({}, {}))
    
    async def remove_inv_key(self, inv_key: str) -> None:
        """Remove an invalidation key and all its full keys."""
        async with self._lock:
            self._inv_to_full.pop(inv_key, None)
            self._inv_meta.pop(inv_key, None)
    
    async def clear_all(self) -> Set[str]:
        """Clear all registry entries and return all full keys."""
        async with self._lock:
            all_keys = set()
            for s in self._inv_to_full.values():
                all_keys.update(s)
            self._inv_to_full.clear()
            self._inv_meta.clear()
            return all_keys


class CacheHistorianDecorator(HistorianPort):
    """
    Caching decorator for HistorianPort with pagination-aware invalidation.
    
    Uses a two-tier cache key structure:
    - Invalidation key: based on filters/query (excludes pagination)
    - Full cache key: includes limit and offset
    
    When data changes, selectively invalidates all paginated pages whose
    filters match the changed record.
    """
    
    def __init__(
        self,
        underlying: HistorianPort,
        ttl: int = 300,  # 5 minutes default (kept for compatibility)
        max_entries: int = 1000,
        query_ttl_seconds: int = 30,
        search_ttl_seconds: int = 60,
    ):
        """
        Initialize cache decorator.
        
        Args:
            underlying: The underlying Historian implementation
            ttl: Default time-to-live for cache entries in seconds (legacy param)
            max_entries: Maximum number of cache entries
            query_ttl_seconds: TTL for query_records operations
            search_ttl_seconds: TTL for search operations
        """
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        
        self._underlying = underlying
        self._ttl = ttl
        self._max_entries = max_entries
        self._query_ttl = query_ttl_seconds
        self._search_ttl = search_ttl_seconds
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()
        self._inflight: Dict[str, asyncio.Event] = {}
        self._registry = InvalidationRegistry()
        self._tracer = get_tracer("src.rcrag.cache")
    
    def _is_fresh(self, timestamp: float, ttl: int) -> bool:
        """Check if a cache entry is still fresh."""
        return (time.time() - timestamp) < ttl
    
    async def _get_if_fresh(self, key: str, ttl: int) -> Optional[Any]:
        """Get cached value if fresh, None otherwise."""
        async with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if self._is_fresh(timestamp, ttl):
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
    
    async def _delete_cache(self, key: str) -> None:
        """Delete a specific cache entry."""
        async with self._lock:
            self._cache.pop(key, None)
    
    async def _invalidate_all(self) -> None:
        """Invalidate all cache entries (called on writes)."""
        full_keys = await self._registry.clear_all()
        for k in full_keys:
            await self._delete_cache(k)
        async with self._lock:
            self._cache.clear()
    
    async def _invalidate_for_record(self, record: HistorianRecord) -> None:
        """
        Invalidate all cached pages (query_records and search) whose filters match this record.
        
        Search caches also include the 'q' parameter; for simplicity we invalidate based on
        filters only. For precise search invalidation, a search index/eventual consistency
        strategy is recommended.
        """
        inv_keys = await self._registry.keys()
        for inv_key in inv_keys:
            filters, extra = await self._registry.get_meta(inv_key)
            # Only filter-based invalidation is supported here
            if self._matches_filters(record, filters):
                full_keys = await self._registry.get_full_keys(inv_key)
                for k in full_keys:
                    await self._delete_cache(k)
                await self._registry.remove_inv_key(inv_key)
    
    def _matches_filters(self, record: HistorianRecord, filters: Dict[str, Any]) -> bool:
        """
        Check if a record matches the given filters using implicit AND semantics.
        
        Supported filters:
        - 'kind': exact match
        - 'namespace': exact match
        - 'metadata': dict of key->value; all must match
        - 'created_after': ISO timestamp (strictly greater than)
        - 'created_before': ISO timestamp (strictly less than)
        """
        if not filters:
            return True
        
        if "kind" in filters and getattr(record, "kind", None) != filters["kind"]:
            return False
        
        if "namespace" in filters and getattr(record, "namespace", None) != filters["namespace"]:
            return False
        
        md = getattr(record, "metadata", {}) or {}
        if "metadata" in filters:
            mf = filters["metadata"] or {}
            for k, v in mf.items():
                if md.get(k) != v:
                    return False
        
        def _parse_iso(s: str) -> datetime:
            # Support trailing 'Z'
            if isinstance(s, str) and s.endswith("Z"):
                s = s[:-1] + "+00:00"
            return datetime.fromisoformat(s)
        
        created_at = getattr(record, "created_at", None)
        if created_at and "created_after" in filters:
            if created_at <= _parse_iso(filters["created_after"]):
                return False
        
        if created_at and "created_before" in filters:
            if created_at >= _parse_iso(filters["created_before"]):
                return False
        
        return True
    
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
            # Now the result should be in cache (use appropriate TTL)
            ttl = self._query_ttl if "query" in method_name else self._search_ttl if "search" in method_name else self._ttl
            return await self._get_if_fresh(key, ttl)
        
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
        Create a record (write operation - invalidates matching cache entries).
        """
        result = await self._underlying.create_record(record)
        # Selective invalidation based on record attributes
        await self._invalidate_for_record(record)
        return result
    
    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        """
        Get a record by ID (cached).
        """
        key = f"get_record:{record_id}"
        
        # Check cache first
        cached = await self._get_if_fresh(key, self._ttl)
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
        key = f"query_by_kind:{kind}:limit={limit}"
        
        # Check cache first
        cached = await self._get_if_fresh(key, self._ttl)
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
        key = f"query_by_provenance:{source_id}"
        
        # Check cache first
        cached = await self._get_if_fresh(key, self._ttl)
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
        limit: int = 10,
        offset: int = 0
    ) -> List[HistorianRecord]:
        """
        Search records (cached with pagination-aware invalidation).
        
        Note: Search invalidation is conservative and filter-based only. When records
        change, we cannot determine if they still match the search query text, so we
        invalidate based on filters alone. For production-scale search with precise
        invalidation, use a dedicated search index with event-based invalidation.
        """
        if offset < 0:
            raise ValueError(f"offset must be >= 0, got {offset}")
        if limit < 0:
            raise ValueError(f"limit must be >= 0, got {limit}")
        
        extra = {"q": query} if query else None
        inv_key, full_key = _make_cache_keys("search", filters, limit, offset, extra=extra)
        
        # Check cache first
        cached = await self._get_if_fresh(full_key, self._search_ttl)
        if cached is not None:
            CACHE_HITS.labels(operation="search").inc()
            return cached
        
        # Cache miss - fetch with inflight coalescing
        async def fetch():
            result = await self._underlying.search(query, filters, limit, offset)
            # Store concrete list to avoid iterator surprises
            data = list(result)
            await self._set_cache(full_key, data)
            await self._registry.register(inv_key, full_key, filters, extra)
            return data
        
        return await self._coalesce_inflight(full_key, "search", fetch())
    
    async def query_records(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[HistorianRecord]:
        """
        Query records with filters (cached with pagination-aware invalidation).
        """
        if offset < 0:
            raise ValueError(f"offset must be >= 0, got {offset}")
        if limit < 0:
            raise ValueError(f"limit must be >= 0, got {limit}")
        
        inv_key, full_key = _make_cache_keys("query_records", filters, limit, offset, extra=None)
        
        # Check cache first
        cached = await self._get_if_fresh(full_key, self._query_ttl)
        if cached is not None:
            CACHE_HITS.labels(operation="query_records").inc()
            return cached
        
        # Cache miss - fetch with inflight coalescing
        async def fetch():
            result = await self._underlying.query_records(filters, limit, offset)
            # Store concrete list to avoid iterator surprises
            data = list(result)
            await self._set_cache(full_key, data)
            await self._registry.register(inv_key, full_key, filters, extra=None)
            return data
        
        return await self._coalesce_inflight(full_key, "query_records", fetch())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._cache),
            "max_entries": self._max_entries,
            "ttl_seconds": self._ttl,
            "query_ttl_seconds": self._query_ttl,
            "search_ttl_seconds": self._search_ttl,
            "inflight_requests": len(self._inflight)
        }
