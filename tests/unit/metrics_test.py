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
        assert m.status_code == 200
        text = m.text
        assert "http_requests_total" in text
        assert "http_request_duration_seconds" in text
        # Expect at least one metric line for /ping
        assert "/ping" in text
