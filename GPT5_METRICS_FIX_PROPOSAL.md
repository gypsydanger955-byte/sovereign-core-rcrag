1. **Root Cause Analysis**

The `/metrics` endpoint returns HTTP 422 (Unprocessable Entity) because FastAPI is rejecting the request due to validation errors on the endpoint's parameters. In FastAPI, a 422 is typically triggered when request parameters or body data do not match the expected schema.

Given the test code, the metrics endpoint is registered via `init_prometheus(app, enabled=True)`. Most Prometheus metrics endpoints are simple GET endpoints that return plain text and do **not** expect any query parameters or request body.

The most likely root cause is that the `/metrics` endpoint handler function is defined with one or more FastAPI parameters that require validation (e.g., query parameters or request body), but the test client calls `/metrics` without those parameters. This mismatch causes FastAPI to reject the request with 422.

Another possibility is that the metrics endpoint is decorated or wrapped by a dependency or middleware that requires input parameters or validates something in the request, but the test client does not provide them.

Because the test uses `AsyncClient` with `ASGITransport`, it calls the route exactly as defined, so any required parameters must be provided.

In summary:

- The `/metrics` endpoint handler expects some query parameters or request body inputs.
- The test calls `/metrics` without any such parameters.
- FastAPI’s validation layer triggers a 422 Unprocessable Entity error.

2. **Proposed Solution**

**Step 1: Inspect and fix the `/metrics` endpoint handler signature**

Look into `init_prometheus` and the implementation of the `/metrics` route it adds. The handler should be:

- A simple GET endpoint without any required parameters.
- Returning plain text content type.
- Not expecting a request body or required query params.

If the handler currently has required parameters, refactor it to remove them or make them optional with defaults.

**Step 2: Fix the `/metrics` route implementation**

Here is a typical minimal example of a Prometheus metrics endpoint in FastAPI:

```python
from fastapi import FastAPI, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

def init_prometheus(app: FastAPI, enabled: bool):
    if not enabled:
        return

    @app.get("/metrics")
    async def metrics():
        # Generate the latest metrics data in Prometheus text format
        data = generate_latest()
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)
```

Make sure your `/metrics` endpoint matches this pattern:

- No parameters in the handler signature.
- Returns a `Response` with content type `text/plain; version=0.0.4` (CONTENT_TYPE_LATEST).
- Uses `prometheus_client.generate_latest()` to produce the metrics string.

**Step 3: Adjust `init_prometheus` if necessary**

If the current implementation of `init_prometheus` registers `/metrics` with parameters (e.g., `query: str` or `request: Request` with validation), remove or make them optional.

3. **Alternative Solutions**

- If the metrics endpoint genuinely needs parameters, update the test to include them accordingly.

- Use an explicit `Depends` with `None` defaults for parameters in the `/metrics` handler to avoid required query parameters.

- If using `APIRouter` or third-party Prometheus instrumentation middleware, verify its configuration to ensure it registers `/metrics` without required parameters.

- Alternatively, test the `/metrics` endpoint using a raw HTTP client (like `httpx` without ASGITransport) to rule out ASGI client-related issues.

4. **Testing Strategy**

- Modify the `/metrics` endpoint to have no required parameters, as shown above.

- Run the test `test_metrics_recorded_and_exported` again; it should pass with HTTP 200.

- Add an integration test calling `/metrics` directly, asserting status 200 and content type `text/plain`.

- Optionally, curl or httpie the running app’s `/metrics` endpoint to verify plain text metrics output.

- Check logs or exceptions for validation errors when calling `/metrics`.

---

### Summary of Proposed Fix with Example Code

```python
# src/rcrag/infrastructure/observability/metrics.py

from fastapi import FastAPI, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

def init_prometheus(app: FastAPI, enabled: bool):
    if not enabled:
        return

    @app.get("/metrics")
    async def metrics():
        data = generate_latest()
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)
```

This ensures `/metrics` is a clean GET with no parameters and will return 200 OK with metrics text.

---

**This fix should resolve the 422 error and make the test pass.**