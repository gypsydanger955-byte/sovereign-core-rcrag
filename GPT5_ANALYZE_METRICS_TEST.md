# GPT-5: Analyze Metrics Test Failure

You are GPT-5, Chief Architect of the Sovereign Core AI Team. A metrics test is failing and needs your analysis.

## Your Task

Analyze the failing test and propose a fix. Be thorough and technical.

## Test Failure Details

**Test:** `test_metrics_recorded_and_exported`  
**Status:** FAILING  
**Error:** `assert 422 == 200` - The `/metrics` endpoint returns 422 (Unprocessable Entity) instead of 200

## Test Code

```python
import asyncio

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from src.rcrag.infrastructure.observability.metrics import REQUEST_COUNT, REQUEST_DURATION, init_prometheus


@pytest.mark.asyncio
async def test_metrics_recorded_and_exported():
    app = FastAPI()
    init_prometheus(app, enabled=True)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Make a few requests
        for _ in range(3):
            resp = await client.get("/ping")
            assert resp.status_code == 200

        # Scrape metrics endpoint
        m = await client.get("/metrics")
        assert m.status_code == 200  # ❌ FAILS HERE - Gets 422
        text = m.text
        assert "http_requests_total" in text
        assert "http_request_duration_seconds" in text
        # Expect at least one metric line for /ping
        assert "/ping" in text
```

## Test Execution Output

```
tests/unit/metrics_test.py::test_metrics_recorded_and_exported FAILED
=================================== FAILURES ===================================
______________________ test_metrics_recorded_and_exported ______________________
    @pytest.mark.asyncio
    async def test_metrics_required_and_exported():
        app = FastAPI()
        init_prometheus(app, enabled=True)
    
        @app.get("/ping")
        async def ping():
            return {"ok": True}
    
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Make a few requests
            for _ in range(3):
                resp = await client.get("/ping")
                assert resp.status_code == 200
    
            # Scrape metrics endpoint
            m = await client.get("/metrics")
>           assert m.status_code == 200
E           assert 422 == 200
E            +  where 422 = <Response [422 Unprocessable Entity]>.status_code
```

## Context

**HTTP 422 (Unprocessable Entity)** typically means:
- FastAPI validation failed
- Request body/params don't match expected schema
- Missing required parameters
- Type mismatch in request data

The `/metrics` endpoint is added by `init_prometheus(app, enabled=True)` and should return Prometheus metrics in text format.

## Your Analysis Should Include

1. **Root Cause:** Why is the `/metrics` endpoint returning 422?
2. **Hypothesis:** What could cause FastAPI to reject the request?
3. **Proposed Fix:** Specific code changes to fix the issue
4. **Verification:** How to verify the fix works

## Response Format

Provide:
1. **Root Cause Analysis**
2. **Proposed Solution** (with code)
3. **Alternative Solutions** (if any)
4. **Testing Strategy**

Be specific and technical. This will be reviewed by Claude.
