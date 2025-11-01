Here's the review and fixes for the failing tests:

---

### 1. Cache Decorator Issues

**File:** `src/rcrag/infrastructure/historian/cache_decorator.py`

**Problem:** `AttributeError: 'CacheDecorator' object has no attribute 'inner'`

The root cause is that the `HistorianDecorator` base class, which `CacheHistor