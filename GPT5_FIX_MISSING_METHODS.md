# GPT-5: Fix Cache Decorator Missing Methods

## Context

We've discovered a critical design mismatch in the RCRAG service that's causing API endpoints to fail.

**See attached:** `SMOKING_GUN_CACHE_METHODS.md`

## The Problem

The API routes are calling methods that don't exist in the HistorianPort interface:
- `search(query, filters, limit)` - Called by `/records/search`
- `query_records(filters, limit)` - Called by `/records` and `/records/search`

But the HistorianPort interface only defines:
- `create_record()`
- `get_record()`
- `query_by_kind()`
- `query_by_provenance()`

## Your Task

Propose a complete fix that:

1. **Resolves the design mismatch**
2. **Makes all API endpoints work**
3. **Maintains the cache decorator pattern**
4. **Minimizes breaking changes**

## Options to Consider

### Option 1: Add methods to interface
- Add `search()` and `query_records()` to HistorianPort
- Implement in all adapters
- Add explicit overrides to cache decorator
- **Pro:** API routes work as-is
- **Con:** Expands interface, more work

### Option 2: Fix API routes
- Change routes to use existing interface methods
- Map `search()` → `query_by_kind()`
- Map `query_records()` → `query_by_kind()`
- **Pro:** Simpler, uses existing interface
- **Con:** Need to update routes

### Option 3: Hybrid approach
- Your creative solution?

## Requirements

1. **All 5 API endpoints must work:**
   - POST `/api/v1/records` (store)
   - GET `/api/v1/records/{id}` (get)
   - GET `/api/v1/records/search` (search)
   - GET `/api/v1/records` (list)
   - GET `/api/v1/stats` (stats)

2. **Cache decorator must have explicit overrides for ALL methods**
   - No relying on `__getattr__`
   - Proper async context management
   - Correct caching behavior

3. **Maintain consistency**
   - Interface, adapters, decorator all aligned
   - Clear method naming
   - Proper type hints

## Deliverables

Please provide:

1. **Recommended Approach**
   - Which option (or hybrid)?
   - Why?
   - Trade-offs?

2. **Complete Implementation Plan**
   - What files need changes?
   - What methods need to be added/changed?
   - Step-by-step implementation order

3. **Code Specifications**
   - Exact method signatures
   - Implementation details
   - Error handling

4. **Testing Strategy**
   - How to verify the fix works?
   - What edge cases to test?

## Success Criteria

- ✅ All API endpoints work
- ✅ Cache decorator has all explicit overrides
- ✅ No `AttributeError` exceptions
- ✅ Hub-RCRAG bridge tests pass
- ✅ Clean, maintainable design

---

**Please provide your complete fix proposal.**
