Certainly! Here's a **complete fix proposal** addressing the mismatch between the API routes and the HistorianPort interface, maintaining the cache decorator pattern, and ensuring minimal breaking changes.

---

# 1. Recommended Approach

### Hybrid Option (Option 3):

- **Add two new methods to the HistorianPort interface:**  
  - `search(query: str, filters: Dict[str, Any], limit: int) -> List[HistorianRecord]`  
  - `query_records(filters: Dict[str, Any], limit: int) -> List[HistorianRecord]`

- **Implement these methods in all adapters** (including in-memory and any DB-backed adapters).

- **Add explicit overrides for these methods in the cache decorator.**

- **Refactor API routes** to call these interface methods exactly (not ad-hoc or legacy methods).

---

### Why Hybrid?

- **API routes are already calling `search` and `query_records`.** Changing routes to use existing methods risks losing semantics or complicating query logic — e.g., `search` implies full text or complex query, which `query_by_kind` may not support.

- **Adding methods to the interface explicitly captures the API's requirements,** preserving clear domain intent.

- **Maintains cache decorator consistency** with explicit overrides for *all* methods.

- **Minimizes breaking changes:** No changes to API routes' logic or signatures.

---

### Trade-offs

| Pros                                           | Cons                                  |
|------------------------------------------------|---------------------------------------|
| Aligns interface with actual API usage         | Requires updates in all adapters      |
| Clear, semantic method separation               | Slightly more code to maintain        |
| Cache decorator remains explicit and robust     | Minor increase in interface surface area |
| No changes to API routes required beyond imports | More initial implementation effort    |

---

# 2. Complete Implementation Plan

| Step | File(s)                              | Change Description                                   |
|-------|------------------------------------|-----------------------------------------------------|
| 1     | `src/rcrag/domain/ports/historian_port.py` | Add `search()` and `query_records()` method signatures to interface. |
| 2     | `src/rcrag/infrastructure/historian/in_memory_adapter.py` (and all other adapters) | Add concrete `search()` and `query_records()` implementations. |
| 3     | `src/rcrag/infrastructure/historian/cache_decorator.py` | Add explicit async overrides for `search()` and `query_records()`. |
| 4     | `src/rcrag/api/routes.py`           | Ensure imports and calls use the new interface methods (likely no code change needed if already calling these methods). |
| 5     | `tests/`                           | Add/update tests covering new methods and cache decorator behavior. |

---

# 3. Code Specifications

---

### 3.1 HistorianPort Interface

```python
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod
from src.rcrag.domain.models import HistorianRecord

class HistorianPort(ABC):

    @abstractmethod
    async def create_record(self, record: HistorianRecord) -> str:
        ...

    @abstractmethod
    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        ...

    @abstractmethod
    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        ...

    @abstractmethod
    async def query_by_provenance(self, source_id: str, limit: int = 10) -> List[HistorianRecord]:
        ...

    @abstractmethod
    async def search(self, query: str, filters: Dict[str, Any], limit: int = 10) -> List[HistorianRecord]:
        """
        Search records based on a free-text query and optional filters.
        """
        ...

    @abstractmethod
    async def query_records(self, filters: Dict[str, Any], limit: int = 10) -> List[HistorianRecord]:
        """
        Query records by arbitrary filters (e.g., date range, kind, provenance).
        """
        ...
```

---

### 3.2 InMemoryAdapter (Example)

```python
from typing import List, Optional, Dict, Any
from src.rcrag.domain.models import HistorianRecord
from src.rcrag.domain.ports.historian_port import HistorianPort

class InMemoryHistorianAdapter(HistorianPort):
    def __init__(self):
        self._records: Dict[str, HistorianRecord] = {}

    async def create_record(self, record: HistorianRecord) -> str:
        self._records[record.id] = record
        return record.id

    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        return self._records.get(record_id)

    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        return [r for r in self._records.values() if r.kind == kind][:limit]

    async def query_by_provenance(self, source_id: str, limit: int = 10) -> List[HistorianRecord]:
        return [r for r in self._records.values() if r.provenance == source_id][:limit]

    async def search(self, query: str, filters: Dict[str, Any], limit: int = 10) -> List[HistorianRecord]:
        # Simple full-text search on record content + filters applied
        results = []
        for r in self._records.values():
            if query.lower() in r.content.lower():
                match = True
                for k, v in filters.items():
                    if getattr(r, k, None) != v:
                        match = False
                        break
                if match:
                    results.append(r)
                    if len(results) >= limit:
                        break
        return results

    async def query_records(self, filters: Dict[str, Any], limit: int = 10) -> List[HistorianRecord]:
        results = []
        for r in self._records.values():
            match = True
            for k, v in filters.items():
                if getattr(r, k, None) != v:
                    match = False
                    break
            if match:
                results.append(r)
                if len(results) >= limit:
                    break
        return results
```

---

### 3.3 Cache Decorator

```python
from typing import List, Optional, Dict, Any
from src.rcrag.domain.models import HistorianRecord
from src.rcrag.domain.ports.historian_port import HistorianPort

class CacheHistorianDecorator(HistorianPort):
    def __init__(self, wrapped: HistorianPort, cache_client):
        self._wrapped = wrapped
        self._cache = cache_client

    async def create_record(self, record: HistorianRecord) -> str:
        record_id = await self._wrapped.create_record(record)
        # Invalidate relevant caches if needed
        await self._cache.delete(f"record:{record_id}")
        return record_id

    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        cache_key = f"record:{record_id}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        record = await self._wrapped.get_record(record_id)
        if record:
            await self._cache.set(cache_key, record)
        return record

    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        cache_key = f"query_by_kind:{kind}:{limit}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        results = await self._wrapped.query_by_kind(kind, limit)
        await self._cache.set(cache_key, results)
        return results

    async def query_by_provenance(self, source_id: str, limit: int = 10) -> List[HistorianRecord]:
        cache_key = f"query_by_provenance:{source_id}:{limit}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        results = await self._wrapped.query_by_provenance(source_id, limit)
        await self._cache.set(cache_key, results)
        return results

    async def search(self, query: str, filters: Dict[str, Any], limit: int = 10) -> List[HistorianRecord]:
        cache_key = f"search:{query}:{str(sorted(filters.items()))}:{limit}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        results = await self._wrapped.search(query, filters, limit)
        await self._cache.set(cache_key, results)
        return results

    async def query_records(self, filters: Dict[str, Any], limit: int = 10) -> List[HistorianRecord]:
        cache_key = f"query_records:{str(sorted(filters.items()))}:{limit}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        results = await self._wrapped.query_records(filters, limit)
        await self._cache.set(cache_key, results)
        return results
```

---

### 3.4 API Routes (`src/rcrag/api/routes.py`)

- Ensure the routes call the `historian.search(...)` and `historian.query_records(...)` methods exactly.

Example:

```python
@router.get("/records/search")
async def search_records(query: str, filters: dict = Depends(...), limit: int = 10):
    records = await historian.search(query=query, filters=filters, limit=limit)
    return records

@router.get("/records")
async def list_records(filters: dict = Depends(...), limit: int = 10):
    records = await historian.query_records(filters=filters, limit=limit)
    return records
```

---

### 3.5 Error Handling

- Raise domain-specific exceptions in adapter methods if invalid filters or bad queries are passed.
- Cache decorator should catch adapter exceptions and propagate them without caching invalid results.
- Validate input parameters in API routes (e.g., limit must be positive integer).
- Return HTTP 400 with validation errors if input is invalid.

---

# 4. Testing Strategy

### 4.1 Unit Tests

- Test `search()` and `query_records()` implementations in each adapter (InMemory, SQL, etc.):
  - Correct filtering behavior
  - Limit respected
  - Case insensitivity for `search`

- Test cache decorator overrides:
  - Cache hit vs miss
  - Cache invalidation on `create_record`
  - Correct cache keys used
  - No falling back to `__getattr__`

### 4.2 Integration Tests

- API endpoint tests for:
  - POST `/api/v1/records` → create record and invalidate cache
  - GET `/api/v1/records/{id}` → get record with caching
  - GET `/api/v1/records/search` → search with filters and limits
  - GET `/api/v1/records` → query records list
  - GET `/api/v1/stats` → verify stats endpoint (ensure no breakage)

- Test error scenarios:
  - Invalid filters
  - Empty results
  - Cache backend failures (simulate)

### 4.3 Edge Cases

- Empty query string to `search()`
- Filters with unknown keys
- Limits of zero or negative values (should raise validation errors)
- Records with missing optional fields

---

# Summary

| Requirement                         | Status After Fix          |
|-----------------------------------|--------------------------|
| All 5 API endpoints work           | ✅                        |
| Cache decorator explicit overrides | ✅                        |
| No AttributeError exceptions       | ✅                        |
| Hub-RCRAG bridge tests pass        | ✅                        |
| Clean, maintainable design          | ✅                        |

---

If you want, I can also provide **diffs/patches** or **full code files** for each step. Just ask!