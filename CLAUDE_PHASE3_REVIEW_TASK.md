# Task for Claude: Review and Fix Phase 3 Implementation

## Context

GPT-5 has implemented Phase 3 of the RCRAG system (production hardening and observability). However, the tests are revealing some issues that need to be fixed.

**Test Results:**
- ✅ 3 tests passing (cache TTL, cache eviction, rate limit within limit)
- ❌ 7 tests failing (cache decorator, rate limit decorator, metrics test)

## Your Mission

Review the Phase 3 code, identify the bugs, and provide fixes for the failing tests.

## Failing Tests

### 1. Cache Decorator Issues
**File:** `src/rcrag/infrastructure/historian/cache_decorator.py`

**Errors:**
```
AttributeError: 'CacheDecorator' object has no attribute 'inner'
```

**Problem:** The decorator is using `self.inner` but should use `self._inner` (consistent with other decorators).

### 2. Rate Limit Decorator Issues
**File:** `src/rcrag/infrastructure/historian/rate_limit_decorator.py`

**Errors:**
```
RecursionError: maximum recursion depth exceeded
```

**Problem:** The `__getattr__` method is causing infinite recursion when trying to access `self.inner`.

### 3. Metrics Test Issues
**File:** `tests/unit/metrics_test.py`

**Errors:**
```
TypeError: AsyncClient.__init__() got an unexpected keyword argument 'app'
```

**Problem:** The test is using old httpx AsyncClient syntax. Modern httpx uses `transport` parameter instead of `app`.

## Files to Review

1. `src/rcrag/infrastructure/historian/cache_decorator.py`
2. `src/rcrag/infrastructure/historian/rate_limit_decorator.py`
3. `tests/unit/metrics_test.py`

## Your Task

For each file, provide:
1. **Root cause analysis**: What's causing the bug?
2. **The fix**: Specific code changes needed
3. **Why it works**: Explanation of why your fix resolves the issue

Please provide the fixes in this format:

```
File: path/to/file.py

Problem: [description]

Fix:
[specific code changes using find/replace format]

Explanation: [why this works]
```

Generate your review and fixes now.
