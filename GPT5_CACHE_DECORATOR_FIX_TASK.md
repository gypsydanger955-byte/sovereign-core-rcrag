# Task for GPT-5: Fix Cache Decorator Bug

## Problem Statement

The `CacheHistorianDecorator` is not caching because it relies on `__getattr__`, but `__getattr__` is never called when the base class `HistorianDecorator` already implements the methods.

## Root Cause

```python
class HistorianDecorator(HistorianPort):
    async def get_record(self, record_id: str):
        return await self._inner.get_record(record_id)  # Direct delegation
    
    async def query_by_kind(self, kind: str, limit: int = 10):
        return await self._inner.query_by_kind(kind, limit=limit)  # Direct delegation

class CacheHistorianDecorator(HistorianDecorator):
    def __getattr__(self, name: str):
        # This is NEVER called for get_record, query_by_kind, etc.
        # because those methods exist in the base class!
        # ... caching logic ...
```

When you call `cached.get_record()`, Python finds the method in `HistorianDecorator` and calls it directly, bypassing the caching logic in `__getattr__`.

## Current Implementation

**File:** `src/rcrag/infrastructure/historian/cache_decorator.py`

The decorator has:
- `_cache: OrderedDict` for LRU caching
- `_ttl: float` for TTL expiration
- `_max: int` for max cache size
- `_make_key()` for generating cache keys
- `_get_if_fresh()` for checking cache hits
- `_evict_if_needed()` for LRU eviction
- `__getattr__()` that creates wrapper functions (but is never called!)

## Your Task

Propose a fix that:
1. **Preserves the existing caching logic** (TTL, LRU, metrics, tracing)
2. **Works with the base class architecture** (inherits from `HistorianDecorator`)
3. **Caches these methods**: `get_record`, `query_by_kind`, `query_by_provenance`
4. **Doesn't cache**: `create_record` (write operations)
5. **Is maintainable** (easy to add new cacheable methods)

## Constraints

- Must inherit from `HistorianDecorator` (don't change the base class)
- Must use the existing `_cache`, `_ttl`, `_max` infrastructure
- Must record `CACHE_HITS` and `CACHE_MISSES` metrics
- Must use OpenTelemetry tracing
- Must be async-safe (handle concurrent access)

## Options to Consider

**Option 1: Override methods explicitly**
```python
async def get_record(self, record_id: str):
    key = self._make_key("get_record", (record_id,), {})
    hit, value = self._get_if_fresh(key)
    if hit:
        CACHE_HITS.labels(operation="get_record").inc()
        return value
    
    # ... cache miss logic ...
```

**Option 2: Use a helper method**
```python
async def _cached_call(self, method_name: str, *args, **kwargs):
    key = self._make_key(method_name, args, kwargs)
    # ... caching logic ...
    
async def get_record(self, record_id: str):
    return await self._cached_call("get_record", record_id)
```

**Option 3: Something else you propose**

## Deliverables

Provide:
1. **Your recommended approach** (which option or a new one)
2. **Complete implementation** of the fixed `CacheHistorianDecorator`
3. **Explanation** of why your approach is best
4. **Any trade-offs** or considerations

Generate your fix now.
