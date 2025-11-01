```
Issue 1: Cache hit test

Root cause: 
The original failing test used a custom mock `MockHistorian` that likely does not increment call count correctly, or the test's call counting logic is flawed. In the shared full test file, the equivalent test uses a `DummyHistorian` with a `calls` dict to track method calls. The failing assertion expecting exactly 1 underlying call failed because the code or test setup called `get_record` twice on the underlying mock.

In general, cache hit tests must confirm the underlying historian is called only once per unique cache key within TTL. The discrepancy suggests the mock or decorator does not share the same cache state or the mock's call counting is faulty.

Fix:
- Use `DummyHistorian` which correctly tracks underlying calls via `calls` dict.
- Use the test pattern in `test_cache_hit_returns_cached_value` from the full test file, which:
  - Calls `await cached.get_record("a1")` twice
  - Asserts the two return values equal
  - Asserts `inner.calls.get("get_record") == 1`
- Avoid mixing different mock classes or duplicated calls.
- Do not redundantly call `get_record` outside the test's core logic that would increment count again unnecessarily.

Here is the adjusted test code (based on full test file):

```python
@pytest.mark.asyncio
async def test_cache_hit_returns_cached_value():
    inner = DummyHistorian()
    cached = CacheHistorianDecorator(inner, ttl_seconds=10, max_size=100)

    # First call, cache miss - underlying called
    v1 = await cached.get_record("a1")
    assert v1 is not None

    # Second call, cache hit - underlying NOT called again
    v2 = await cached.get_record("a1")
    assert v2 is not None
    assert v2 == v1

    # Confirm underlying called exactly once.
    assert inner.calls.get("get_record") == 1
```

---

Issue 2: DummyHistorian query_by_kind signature

Root cause:
The `DummyHistorian.query_by_kind` method lacks the `limit` keyword argument that the real `HistorianPort` interface and `CacheHistorianDecorator` expect. The decorator or code under test calls `query_by_kind` with `limit=...` keyword argument, causing a `TypeError`.

Fix:
Modify `DummyHistorian.query_by_kind` to accept the `limit` keyword argument (with an optional default) matching the interface, e.g.

```python
async def query_by_kind(self, kind: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    self.calls["query_by_kind"] = self.calls.get("query_by_kind", 0) + 1
    # Return up to limit results if limit is specified
    results = [{"id": "1", "kind": kind}, {"id": "2", "kind": kind}]
    if limit is not None:
        return results[:limit]
    return results
```

This prevents the unexpected keyword argument error and maintains compatible behavior for tests relying on `query_by_kind`.


---

Summary of fixes:

```python
# Fix for Issue 1
@pytest.mark.asyncio
async def test_cache_hit_returns_cached_value():
    inner = DummyHistorian()
    cached = CacheHistorianDecorator(inner, ttl_seconds=10, max_size=100)

    v1 = await cached.get_record("a1")
    v2 = await cached.get_record("a1")
    assert v1 == v2
    assert inner.calls.get("get_record") == 1

# Fix for Issue 2, modify DummyHistorian:
class DummyHistorian:
    def __init__(self):
        self.calls: Dict[str, int] = {}

    async def get_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        self.calls["get_record"] = self.calls.get("get_record", 0) + 1
        return {"id": record_id, "value": f"val-{record_id}"}

    # Add 'limit' keyword argument to match interface
    async def query_by_kind(self, kind: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        self.calls["query_by_kind"] = self.calls.get("query_by_kind", 0) + 1
        results = [{"id": "1", "kind": kind}, {"id": "2", "kind": kind}]
        if limit is not None:
            return results[:limit]
        return results

    async def create_record(self, record: Dict[str, Any]) -> str:
        self.calls["create_record"] = self.calls.get("create_record", 0) + 1
        return "ok"
```
