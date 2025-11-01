# 🔫 Smoking Gun Report: Cache Decorator Missing Methods

## The Problem

The cache decorator is missing explicit method overrides, causing `AttributeError` when API routes try to call methods that aren't explicitly defined.

## Smoking Gun #1: HistorianPort Interface (What SHOULD exist)

```python
# From src/rcrag/domain/ports/historian_port.py

async def create_record(self, record: HistorianRecord) -> str
async def get_record(self, record_id: str) -> Optional[HistorianRecord]
async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]
async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]
```

**Total: 4 methods in the interface**

## Smoking Gun #2: API Routes Calling Methods (What's ACTUALLY being called)

```python
# From src/rcrag/api/routes.py

Line 80:  record_id = await historian.create_record(record)           ✅ EXISTS
Line 111: records = await historian.search(query=query, ...)          ❌ MISSING!
Line 113: records = await historian.query_records(filters=...)        ❌ MISSING!
Line 140: record = await historian.get_record(record_id)              ✅ EXISTS
Line 160: records = await historian.query_records(...)                ❌ MISSING!
```

**Problem:** API routes are calling methods that DON'T exist in the HistorianPort interface!

## Smoking Gun #3: Cache Decorator Explicit Overrides (What's implemented)

```python
# From src/rcrag/infrastructure/historian/cache_decorator.py

async def create_record(self, record: Any) -> str                     ✅
async def get_record(self, record_id: str) -> Any                     ✅
async def query_by_kind(self, kind: str, limit: int = 100) -> Any    ✅
async def query_by_provenance(self, source: str, limit: int = 100)   ✅
```

**Total: 4 explicit overrides**

## Smoking Gun #4: What's MISSING?

### Methods API routes are calling but don't exist anywhere:

1. ❌ **`search(query, filters, limit)`** - Called by `/records/search` endpoint
2. ❌ **`query_records(filters, limit)`** - Called by `/records/search` and `/records` endpoints

### Root Cause

The API routes were written to call methods that were NEVER defined in the HistorianPort interface!

**This is a design mismatch:**
- HistorianPort defines: `create_record`, `get_record`, `query_by_kind`, `query_by_provenance`
- API routes expect: `search`, `query_records`
- Cache decorator has: Only the 4 HistorianPort methods

## The Fix Needed

**Option 1: Add missing methods to HistorianPort interface**
- Add `search()` method
- Add `query_records()` method
- Implement in all adapters (InMemoryAdapter, etc.)
- Add explicit overrides to cache decorator

**Option 2: Fix API routes to use existing methods**
- Change `search()` calls to use `query_by_kind()`
- Change `query_records()` calls to use `query_by_kind()`
- No interface changes needed

**Recommendation:** Option 2 is simpler and safer - use existing interface methods.

## Evidence

**Test failure:**
```
RCRAGServerError: Server error: {"detail":"Failed to search records: 
'CacheHistorianDecorator' object has no attribute 'query_records'"}
```

**Previous similar failure:**
```
RCRAGServerError: Server error: {"detail":"Failed to store record: 
'CacheHistorianDecorator' object has no attribute 'store_record'"}
```

## Impact

**Current state:**
- ✅ `create_record` works
- ✅ `get_record` works  
- ❌ `/records/search` endpoint BROKEN
- ❌ `/records` list endpoint BROKEN

**Affected functionality:**
- Hub agents can store records
- Hub agents can get records by ID
- Hub agents CANNOT search records
- Hub agents CANNOT list records by kind

This blocks the bridge from being fully functional!
