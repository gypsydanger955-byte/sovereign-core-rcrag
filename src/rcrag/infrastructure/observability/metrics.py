import time
from typing import Callable, Optional

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


# HTTP metrics
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "Duration of HTTP requests in seconds",
    ["endpoint", "method"],
)
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["endpoint", "method", "status_code"],
)

# Circuit breaker state: closed=0, open=1, half_open=2
CIRCUIT_BREAKER_STATE = Gauge(
    "rcrag_circuit_breaker_state",
    "Circuit breaker state by name (closed=0, open=1, half_open=2)",
    ["name"],
)

# Historian metrics
HISTORIAN_OPERATION_DURATION = Histogram(
    "rcrag_historian_operation_duration_seconds",
    "Duration of historian operations in seconds",
    ["operation"],
)

CACHE_HITS = Counter(
    "rcrag_cache_hits_total",
    "Total cache hits",
    ["operation"],
)
CACHE_MISSES = Counter(
    "rcrag_cache_misses_total",
    "Total cache misses",
    ["operation"],
)

RATE_LIMIT_HITS = Counter(
    "rcrag_rate_limit_hits_total",
    "Total rate limit hits",
    ["operation"],
)

ERROR_COUNT = Counter(
    "rcrag_errors_total",
    "Total error count",
    ["type"],
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        start = time.perf_counter()
        try:
            response = await call_next(request)
            status_code = getattr(response, "status_code", 500)
            return response
        finally:
            elapsed = time.perf_counter() - start
            endpoint = self._route_template(request)
            REQUEST_DURATION.labels(endpoint=endpoint, method=request.method).observe(elapsed)
            REQUEST_COUNT.labels(endpoint=endpoint, method=request.method, status_code=str(status_code)).inc()

    @staticmethod
    def _route_template(request: Request) -> str:
        # Try route path template, else raw path
        try:
            route = request.scope.get("route")
            if route and hasattr(route, "path"):
                return getattr(route, "path", request.url.path)
        except Exception:  # pragma: no cover
            pass
        return request.url.path


async def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint - returns metrics in text format."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def init_prometheus(app, enabled: bool = True):
    if not enabled:
        return
    # Avoid duplicate middleware and route registration
    # Starlette doesn't have a direct way to inspect middleware uniqueness, so rely on path check
    paths = {getattr(r, "path", None) for r in getattr(app, "routes", [])}
    if "/metrics" not in paths:
        app.add_api_route("/metrics", metrics_endpoint, methods=["GET"])
    # Check for existing PrometheusMiddleware
    middlewares = getattr(app, "user_middleware", [])
    if not any(getattr(m, "cls", None) is PrometheusMiddleware for m in middlewares):
        app.add_middleware(PrometheusMiddleware)


def record_circuit_breaker_state(name: str, state: int) -> None:
    """
    Helper to expose circuit breaker state to Prometheus.
    """
    CIRCUIT_BREAKER_STATE.labels(name=name).set(float(state))


def record_error(error_type: str) -> None:
    ERROR_COUNT.labels(type=error_type).inc()
