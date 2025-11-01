# Task for Claude: Fix Remaining Phase 3 Test Issues

## Context

We have 2 failing tests in Phase 3. The core functionality works (rate limiting, caching), but there are test logic issues.

## Failing Tests

### 1. test_cache_hit_returns_cached_value

**Error:**
```
AssertionError: assert 2 == 1
```

**Test Code:**
```python
async def test_cache_hit_returns_cached_value():
    mock = MockHistorian()
    cached = CacheHistorianDecorator(mock, ttl_seconds=10.0, max_size=100)
    
    # First call: cache miss
    r1 = await cached.get_record("id1")
    assert r1 is not None
    
    # Second call: should be cache hit
    r2 = await cached.get_record("id1")
    assert r2 is not None
    assert r2 == r1
    
    # Mock should only be called once
    assert mock.call_count == 1  # FAILS: call_count is 2
```

**Problem:** The test expects the mock to be called once, but it's being called twice. Why?

### 2. test_cache_metrics_hit_miss

**Error:**
```
TypeError: DummyHistorian.query_by_kind() got an unexpected keyword argument 'limit'
```

**Test Code:**
```python
class DummyHistorian:
    async def get_record(self, record_id: str):
        return HistorianRecord(...)
    
    async def query_by_kind(self, kind: str):  # Missing 'limit' parameter
        return []
```

**Problem:** The `DummyHistorian` fixture doesn't match the `HistorianPort` interface which requires `limit` parameter.

## Your Task

Provide fixes for both issues:

1. **For test_cache_hit_returns_cached_value**: Explain why the mock is being called twice and how to fix the test logic.

2. **For test_cache_metrics_hit_miss**: Fix the `DummyHistorian` class to match the `HistorianPort` interface.

Provide fixes in this format:

```
Issue 1: Cache hit test

Root cause: [explanation]

Fix:
[code changes]
```
