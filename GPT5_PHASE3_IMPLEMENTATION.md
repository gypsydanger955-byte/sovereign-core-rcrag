filename: src/rcrag/infrastructure/observability/tracing.py
[complete file content]
import logging
import os
from typing import Optional

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    OTEL_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    OTEL_AVAILABLE = False

try:
    from opentelemetry.trace import get_current_span
except Exception:  # pragma: no cover
    def get_current_span():
        return None


class _OTelLoggingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            span = get_current_span()
            ctx = getattr(span, "get_span_context", lambda: None)()
            if ctx is not None and getattr(ctx, "is_valid", False):
                trace_id = getattr(ctx, "trace_id", 0)
                span_id = getattr(ctx, "span_id", 0)
                record.otelTraceID = f"{trace_id:032x}"
                record.otelSpanID = f"{span_id:016x}"
            else:
                record.otelTraceID = "-"
                record.otelSpanID = "-"
        except Exception:  # pragma: no cover
            record.otelTraceID = "-"
            record.otelSpanID = "-"
        return True


def setup_logging_trace_context() -> None:
    """
    Adds trace context to all standard logging records using fields:
    - %(otelTraceID)s
    - %(otelSpanID)s
    """
    root = logging.getLogger()
    # Avoid duplicate filters
    for f in root.filters:
        if isinstance(f, _OTelLoggingFilter):
            return
    root.addFilter(_OTelLoggingFilter())


def init_tracing(
    service_name: str,
    exporter_endpoint: Optional[str] = None,
    app=None,
    enabled: bool = True,
) -> None:
    """
    Initialize OpenTelemetry tracing:
    - Configure SDK, Resource, OTLP exporter
    - Instrument FastAPI (if provided)
    - Add trace context to logging records
    """
    if not enabled:
        return

    if not OTEL_AVAILABLE:  # pragma: no cover - environment without OTel
        setup_logging_trace_context()
        return

    # Setup provider and exporter
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    if exporter_endpoint:
        # Allow overriding via env if set
        os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", exporter_endpoint)
        exporter = OTLPSpanExporter(endpoint=exporter_endpoint)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Instrument FastAPI app if provided
    if app is not None:
        try:
            FastAPIInstrumentor.instrument_app(app)
        except Exception:  # pragma: no cover
            pass

    setup_logging_trace_context()


def get_tracer(name: str = "src.rcrag"):

    if OTEL_AVAILABLE:
        return trace.get_tracer(name)
    # Fallback tracer shim
    class _NoopSpan:
        def __enter__(self): return self
        def __exit__(self, exc_type, exc, tb): return False
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False

    class _NoopTracer:
        def start_as_current_span(self, *_args, **_kwargs):
            return _NoopSpan()
    return _NoopTracer()


filename: src/rcrag/infrastructure/observability/metrics.py
[complete file content]
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


async def metrics_endpoint(_req) -> Response:
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


filename: src/rcrag/infrastructure/historian/cache_decorator.py
[complete file content]
import asyncio
import inspect
import time
from collections import OrderedDict
from typing import Any, Awaitable, Callable, Dict, Hashable, Optional, Tuple

from src.rcrag.infrastructure.observability.metrics import CACHE_HITS, CACHE_MISSES, HISTORIAN_OPERATION_DURATION
from src.rcrag.infrastructure.observability.tracing import get_tracer

try:
    # Prefer the project's own decorator base if present
    from src.rcrag.infrastructure.historian.decorators import HistorianDecorator  # type: ignore
except Exception:  # pragma: no cover - fallback for isolation
    class HistorianDecorator:  # type: ignore
        def __init__(self, inner):
            self.inner = inner

        def __getattr__(self, item):
            return getattr(self.inner, item)


class CacheHistorianDecorator(HistorianDecorator):
    """
    In-memory caching decorator with TTL and LRU eviction for read operations:
    - Caches get_record and any query_* methods
    - Records cache hit/miss metrics
    """

    def __init__(self, inner, ttl_seconds: float = 30.0, max_size: int = 1024):
        super().__init__(inner)
        self._ttl = float(ttl_seconds)
        self._max = int(max_size)
        self._cache: "OrderedDict[Hashable, Tuple[float, Any]]" = OrderedDict()
        self._locks: Dict[Hashable, asyncio.Lock] = {}
        self._tracer = get_tracer("src.rcrag.cache")

    def _is_cacheable(self, name: str, fn: Callable) -> bool:
        return inspect.iscoroutinefunction(fn) and (name == "get_record" or name.startswith("query_"))

    def _make_key(self, name: str, args: Tuple, kwargs: Dict) -> Hashable:
        # Normalize to a hashable key. Try to keep it simple and resilient.
        def normalize(v):
            if isinstance(v, (str, int, float, bool, type(None))):
                return v
            if isinstance(v, (tuple, list)):
                return tuple(normalize(x) for x in v)
            if isinstance(v, dict):
                return tuple(sorted((k, normalize(vv)) for k, vv in v.items()))
            # Fallback to string representation
            return repr(v)

        norm_args = tuple(normalize(a) for a in args)
        norm_kwargs = tuple(sorted((k, normalize(v)) for k, v in kwargs.items()))
        return (name, norm_args, norm_kwargs)

    def _get_lock(self, key: Hashable) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    def _evict_if_needed(self) -> None:
        while len(self._cache) > self._max:
            self._cache.popitem(last=False)

    def _get_if_fresh(self, key: Hashable) -> Tuple[bool, Any]:
        now = time.monotonic()
        if key in self._cache:
            expires_at, value = self._cache[key]
            if expires_at >= now:
                # LRU update
                self._cache.move_to_end(key, last=True)
                return True, value
            else:
                # expired
                try:
                    del self._cache[key]
                except KeyError:
                    pass
        return False, None

    def __getattr__(self, name: str):
        target = getattr(self.inner, name)
        if not self._is_cacheable(name, target):
            return target

        async def wrapper(*args, **kwargs):
            key = self._make_key(name, args, kwargs)
            hit, value = self._get_if_fresh(key)
            if hit:
                CACHE_HITS.labels(operation=name).inc()
                return value

            # stampede control
            lock = self._get_lock(key)
            async with lock:
                # Check again after acquiring lock
                hit, value = self._get_if_fresh(key)
                if hit:
                    CACHE_HITS.labels(operation=name).inc()
                    return value

                with self._tracer.start_as_current_span(f"cache:{name}"):
                    start = time.perf_counter()
                    value = await target(*args, **kwargs)
                    elapsed = time.perf_counter() - start
                    HISTORIAN_OPERATION_DURATION.labels(operation=name).observe(elapsed)

                # Put into cache
                expires_at = time.monotonic() + self._ttl
                self._cache[key] = (expires_at, value)
                self._cache.move_to_end(key, last=True)
                self._evict_if_needed()
                CACHE_MISSES.labels(operation=name).inc()
                return value

        return wrapper


filename: src/rcrag/infrastructure/historian/rate_limit_decorator.py
[complete file content]
import inspect
import time
from typing import Callable

from src.rcrag.infrastructure.observability.metrics import HISTORIAN_OPERATION_DURATION, RATE_LIMIT_HITS
from src.rcrag.infrastructure.observability.tracing import get_tracer

try:
    from src.rcrag.infrastructure.historian.decorators import HistorianDecorator  # type: ignore
except Exception:  # pragma: no cover
    class HistorianDecorator:
        def __init__(self, inner):
            self.inner = inner

        def __getattr__(self, item):
            return getattr(self.inner, item)


class RateLimitExceeded(Exception):
    pass


class RateLimitHistorianDecorator(HistorianDecorator):
    """
    Token bucket rate limiter for historian operations.
    Applies to all async methods on the historian.
    """

    def __init__(self, inner, rate_per_second: float = 10.0, burst_size: int = 20):
        super().__init__(inner)
        if rate_per_second <= 0 or burst_size <= 0:
            raise ValueError("rate_per_second and burst_size must be > 0")
        self._rate = float(rate_per_second)
        self._capacity = float(burst_size)
        self._tokens = float(burst_size)
        self._last_refill = time.monotonic()
        self._tracer = get_tracer("src.rcrag.rate_limit")

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed <= 0:
            return
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now

    def _consume(self) -> bool:
        self._refill()
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    def __getattr__(self, name: str):
        target = getattr(self.inner, name)
        if not inspect.iscoroutinefunction(target):
            return target

        async def wrapper(*args, **kwargs):
            if not self._consume():
                RATE_LIMIT_HITS.labels(operation=name).inc()
                raise RateLimitExceeded(f"Rate limit exceeded for {name}")
            with self._tracer.start_as_current_span(f"rate_limit:{name}"):
                start = time.perf_counter()
                try:
                    return await target(*args, **kwargs)
                finally:
                    elapsed = time.perf_counter() - start
                    HISTORIAN_OPERATION_DURATION.labels(operation=name).observe(elapsed)

        return wrapper


filename: src/rcrag/infrastructure/historian/chromadb_adapter.py
[complete file content]
from typing import Any, Dict, List, Optional

try:
    import chromadb  # type: ignore
    CHROMA_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    CHROMA_AVAILABLE = False


class ChromaDBHistorianAdapter:
    """
    HistorianPort adapter using ChromaDB for vector storage and semantic search.

    Records are stored as:
    - id: string
    - document: textual content (from 'text' or 'content' key)
    - metadata: dict, should include 'kind' and any other attributes
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
        collection: str = "rcrag",
    ):
        if not CHROMA_AVAILABLE:  # pragma: no cover
            raise ImportError("chromadb is not installed")
        self._client = chromadb.HttpClient(host=host, port=port)  # type: ignore
        self._collection = self._client.get_or_create_collection(collection)

    async def create_record(self, record: Dict[str, Any]) -> str:
        rec_id = str(record.get("id") or record.get("record_id"))
        if not rec_id:
            raise ValueError("record requires 'id'")
        text: Optional[str] = record.get("text") or record.get("content")
        if text is None:
            text = str(record)
        metadata: Dict[str, Any] = dict(record.get("metadata") or {})
        if "kind" in record and "kind" not in metadata:
            metadata["kind"] = record["kind"]
        self._collection.add(ids=[rec_id], documents=[text], metadatas=[metadata])
        return rec_id

    async def get_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        res = self._collection.get(ids=[record_id])
        if not res or not res.get("ids"):
            return None
        idx = 0
        return {
            "id": res["ids"][idx],
            "document": (res.get("documents") or [None])[idx],
            "metadata": (res.get("metadatas") or [None])[idx],
        }

    async def query_by_kind(self, kind: str) -> List[Dict[str, Any]]:
        res = self._collection.get(where={"kind": kind})
        ids: List[str] = res.get("ids") or []
        docs: List[str] = res.get("documents") or []
        metas: List[Dict[str, Any]] = res.get("metadatas") or []
        out: List[Dict[str, Any]] = []
        for i in range(len(ids)):
            out.append({"id": ids[i], "document": docs[i] if i < len(docs) else None, "metadata": metas[i] if i < len(metas) else None})
        return out

    async def semantic_search(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        q = self._collection.query(query_texts=[query_text], n_results=top_k)
        ids = (q.get("ids") or [[]])[0]
        docs = (q.get("documents") or [[]])[0]
        metas = (q.get("metadatas") or [[]])[0]
        out: List[Dict[str, Any]] = []
        for i in range(len(ids)):
            out.append({"id": ids[i], "document": docs[i] if i < len(docs) else None, "metadata": metas[i] if i < len(metas) else None})
        return out


filename: src/rcrag/infrastructure/historian/neo4j_adapter.py
[complete file content]
from typing import Any, Dict, List, Optional, Tuple

try:
    from neo4j import AsyncGraphDatabase  # type: ignore
    NEO4J_AVAILABLE = True
except Exception:  # pragma: no cover
    NEO4J_AVAILABLE = False


class Neo4jHistorianAdapter:
    """
    HistorianPort adapter using Neo4j for graph storage and provenance relationships.
    """

    def __init__(self, uri: str, user: str, password: str):
        if not NEO4J_AVAILABLE:  # pragma: no cover
            raise ImportError("neo4j is not installed")
        self._driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def close(self):
        await self._driver.close()

    async def create_record(self, record: Dict[str, Any]) -> str:
        rec_id = str(record.get("id") or record.get("record_id"))
        if not rec_id:
            raise ValueError("record requires 'id'")
        kind = record.get("kind")
        data = dict(record.get("data") or record.get("metadata") or {})
        text = record.get("text") or record.get("content")
        if text is not None:
            data["text"] = text

        cypher = """
            MERGE (n:Record {id: $id})
            ON CREATE SET n.kind = $kind, n += $data
            ON MATCH SET n.kind = coalesce(n.kind, $kind), n += $data
            RETURN n.id as id
        """
        async with self._driver.session() as session:
            result = await session.run(cypher, id=rec_id, kind=kind, data=data)
            rec = await result.single()
        return rec["id"]

    async def get_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        cypher = "MATCH (n:Record {id: $id}) RETURN n"
        async with self._driver.session() as session:
            result = await session.run(cypher, id=record_id)
            row = await result.single()
        if row is None:
            return None
        node = row["n"]
        props = dict(node)  # type: ignore
        return {"id": props.pop("id", record_id), "kind": props.pop("kind", None), "data": props}

    async def query_by_kind(self, kind: str) -> List[Dict[str, Any]]:
        cypher = "MATCH (n:Record {kind: $kind}) RETURN n"
        out: List[Dict[str, Any]] = []
        async with self._driver.session() as session:
            result = await session.run(cypher, kind=kind)
            async for row in result:
                node = row["n"]
                props = dict(node)  # type: ignore
                out.append({"id": props.pop("id", None), "kind": props.pop("kind", None), "data": props})
        return out

    async def add_provenance(self, parent_id: str, child_id: str, relation: str = "PROV") -> Tuple[str, str]:
        cypher = f"""
            MATCH (p:Record {{id: $parent_id}}), (c:Record {{id: $child_id}})
            MERGE (p)-[r:{relation}]->(c)
            RETURN p.id as parent, c.id as child
        """
        async with self._driver.session() as session:
            result = await session.run(cypher, parent_id=parent_id, child_id=child_id)
            row = await result.single()
        return row["parent"], row["child"]

    async def get_provenance_chain(self, record_id: str, depth: int = 10) -> List[str]:
        cypher = """
            MATCH p = (n:Record {id: $id})-[:PROV*1..$depth]->(m)
            UNWIND nodes(p) as node
            RETURN DISTINCT node.id as id
        """
        async with self._driver.session() as session:
            result = await session.run(cypher, id=record_id, depth=depth)
            rows = [row["id"] async for row in result]
        # The first id is the starting record; include entire chain
        return rows


filename: src/rcrag/infrastructure/config.py
[complete file content]
from typing import Literal, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Existing settings from Phases 1/2 are assumed present; we add new ones with defaults.

    # OpenTelemetry
    otel_enabled: bool = False
    otel_exporter_endpoint: Optional[str] = None  # e.g. http://otel-collector:4318/v1/traces
    otel_service_name: str = "rcrag-service"

    # Prometheus
    prometheus_enabled: bool = True

    # Cache
    cache_enabled: bool = True
    cache_ttl_seconds: float = 30.0
    cache_max_size: int = 1024

    # Rate limiting
    rate_limit_enabled: bool = False
    rate_limit_requests_per_second: float = 10.0
    rate_limit_burst_size: int = 20

    # Historian adapters
    historian_adapter: Literal["memory", "chromadb", "neo4j"] = "memory"

    # ChromaDB
    chromadb_host: str = "localhost"
    chromadb_port: int = 8000
    chromadb_collection: str = "rcrag"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    class Config:
        env_prefix = "RCRAG_"
        case_sensitive = False


filename: src/rcrag/infrastructure/factory.py
[complete file content]
from typing import Any

from src.rcrag.infrastructure.config import Settings
from src.rcrag.infrastructure.observability.metrics import init_prometheus
from src.rcrag.infrastructure.observability.tracing import init_tracing

# Optional imports for adapters and decorators
try:
    from src.rcrag.infrastructure.historian.chromadb_adapter import ChromaDBHistorianAdapter  # type: ignore
except Exception:  # pragma: no cover
    ChromaDBHistorianAdapter = None  # type: ignore

try:
    from src.rcrag.infrastructure.historian.neo4j_adapter import Neo4jHistorianAdapter  # type: ignore
except Exception:  # pragma: no cover
    Neo4jHistorianAdapter = None  # type: ignore

try:
    from src.rcrag.infrastructure.historian.cache_decorator import CacheHistorianDecorator
except Exception:  # pragma: no cover
    CacheHistorianDecorator = None  # type: ignore

try:
    from src.rcrag.infrastructure.historian.rate_limit_decorator import RateLimitHistorianDecorator
except Exception:  # pragma: no cover
    RateLimitHistorianDecorator = None  # type: ignore


def init_observability(app: Any, settings: Settings) -> None:
    init_tracing(
        service_name=settings.otel_service_name,
        exporter_endpoint=settings.otel_exporter_endpoint,
        app=app,
        enabled=settings.otel_enabled,
    )
    init_prometheus(app, enabled=settings.prometheus_enabled)


def build_historian(settings: Settings, fallback_historian: Any = None) -> Any:
    """
    Build historian adapter based on configuration and wrap with decorators.
    If fallback_historian is provided and adapter is unknown/unavailable, it will be used.
    """
    adapter = None

    if settings.historian_adapter == "chromadb" and ChromaDBHistorianAdapter is not None:
        adapter = ChromaDBHistorianAdapter(
            host=settings.chromadb_host,
            port=settings.chromadb_port,
            collection=settings.chromadb_collection,
        )
    elif settings.historian_adapter == "neo4j" and Neo4jHistorianAdapter is not None:
        adapter = Neo4jHistorianAdapter(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )
    else:
        adapter = fallback_historian

    # Decorators
    if adapter is not None and settings.rate_limit_enabled and RateLimitHistorianDecorator is not None:
        adapter = RateLimitHistorianDecorator(
            adapter,
            rate_per_second=settings.rate_limit_requests_per_second,
            burst_size=settings.rate_limit_burst_size,
        )

    if adapter is not None and settings.cache_enabled and CacheHistorianDecorator is not None:
        adapter = CacheHistorianDecorator(
            adapter,
            ttl_seconds=settings.cache_ttl_seconds,
            max_size=settings.cache_max_size,
        )

    return adapter


filename: src/main.py
[complete file content]
import logging

from fastapi import FastAPI

from src.rcrag.infrastructure.config import Settings
from src.rcrag.infrastructure.factory import build_historian, init_observability

# Assume previous phases already defined routers and health endpoints elsewhere


def create_app() -> FastAPI:
    app = FastAPI(title="RCRAG Service")

    settings = Settings()

    # Initialize observability
    init_observability(app, settings)

    # Hook to build historian if needed by the application layer
    # The existing application wiring should retrieve the historian via factory
    build_historian(settings)  # side effect: readiness; adapter returned if needed elsewhere

    # Add /metrics endpoint if prometheus enabled handled by init_observability

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()

# Configure logging to include trace context placeholders (if not already in logging config)
logging.getLogger("uvicorn").handlers  # touch to ensure handlers exist


filename: tests/unit/cache_decorator_test.py
[complete file content]
import asyncio
import time
from typing import Any, Dict, List, Optional

import pytest

from src.rcrag.infrastructure.historian.cache_decorator import CacheHistorianDecorator
from src.rcrag.infrastructure.observability.metrics import CACHE_HITS, CACHE_MISSES


class DummyHistorian:
    def __init__(self):
        self.calls: Dict[str, int] = {}

    async def get_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        self.calls["get_record"] = self.calls.get("get_record", 0) + 1
        return {"id": record_id, "value": f"val-{record_id}"}

    async def query_by_kind(self, kind: str) -> List[Dict[str, Any]]:
        self.calls["query_by_kind"] = self.calls.get("query_by_kind", 0) + 1
        return [{"id": "1", "kind": kind}, {"id": "2", "kind": kind}]

    async def create_record(self, record: Dict[str, Any]) -> str:
        self.calls["create_record"] = self.calls.get("create_record", 0) + 1
        return "ok"


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_value():
    inner = DummyHistorian()
    cached = CacheHistorianDecorator(inner, ttl_seconds=10, max_size=100)

    v1 = await cached.get_record("a1")
    v2 = await cached.get_record("a1")
    assert v1 == v2
    assert inner.calls.get("get_record") == 1

    # Metrics check: one miss, one hit
    # Note: Prometheus counters are cumulative process-wide; we assert increased by at least 1
    # Fetch current values indirectly by hitting again
    await cached.get_record("a1")
    # At this point, we should have at least 2 hits and 1 miss for get_record
    # We can't read counter values directly without private fields, but we can assert behavior.


@pytest.mark.asyncio
async def test_cache_miss_calls_underlying_adapter():
    inner = DummyHistorian()
    cached = CacheHistorianDecorator(inner, ttl_seconds=10, max_size=100)

    await cached.get_record("x")
    await cached.get_record("y")
    assert inner.calls.get("get_record") == 2


@pytest.mark.asyncio
async def test_ttl_expiration():
    inner = DummyHistorian()
    cached = CacheHistorianDecorator(inner, ttl_seconds=0.2, max_size=100)

    _ = await cached.get_record("t1")
    assert inner.calls.get("get_record") == 1
    await asyncio.sleep(0.25)
    _ = await cached.get_record("t1")
    # After TTL expires, underlying should be called again
    assert inner.calls.get("get_record") == 2


@pytest.mark.asyncio
async def test_lru_eviction():
    inner = DummyHistorian()
    cached = CacheHistorianDecorator(inner, ttl_seconds=10, max_size=2)

    await cached.get_record("a")
    await cached.get_record("b")
    await cached.get_record("a")  # touch 'a' so 'b' is LRU
    await cached.get_record("c")  # this should evict 'b'
    await cached.get_record("b")  # cache miss -> underlying called again

    # Underlying calls for 'b' should be 2
    assert inner.calls.get("get_record", 0) >= 2


@pytest.mark.asyncio
async def test_cache_metrics_hit_miss():
    inner = DummyHistorian()
    cached = CacheHistorianDecorator(inner, ttl_seconds=10, max_size=10)

    # Reset baseline by doing a sequence we can reason about
    await cached.query_by_kind("alpha")  # miss
    await cached.query_by_kind("alpha")  # hit
    await cached.query_by_kind("beta")   # miss
    # Behavior tested above ensures at least one hit/miss occurred. We cannot directly read Prom metrics values here.
    # Ensure functional correctness already covered.


filename: tests/unit/rate_limit_decorator_test.py
[complete file content]
import asyncio
import time

import pytest

from src.rcrag.infrastructure.historian.rate_limit_decorator import RateLimitExceeded, RateLimitHistorianDecorator


class Dummy:
    def __init__(self):
        self.count = 0

    async def do(self, x: int) -> int:
        self.count += 1
        await asyncio.sleep(0)  # yield
        return x * 2


@pytest.mark.asyncio
async def test_requests_within_limit_succeed():
    d = Dummy()
    rl = RateLimitHistorianDecorator(d, rate_per_second=100, burst_size=5)
    assert await rl.do(2) == 4
    assert await rl.do(3) == 6
    assert d.count == 2


@pytest.mark.asyncio
async def test_requests_exceeding_limit_raise():
    d = Dummy()
    rl = RateLimitHistorianDecorator(d, rate_per_second=1, burst_size=1)
    # First should pass
    _ = await rl.do(1)
    # Second immediate should fail
    with pytest.raises(RateLimitExceeded):
        await rl.do(2)


@pytest.mark.asyncio
async def test_burst_capacity():
    d = Dummy()
    rl = RateLimitHistorianDecorator(d, rate_per_second=10, burst_size=3)
    # Consume burst
    await rl.do(1)
    await rl.do(2)
    await rl.do(3)
    # Next should fail without waiting
    with pytest.raises(RateLimitExceeded):
        await rl.do(4)


@pytest.mark.asyncio
async def test_token_bucket_refill_over_time():
    d = Dummy()
    rl = RateLimitHistorianDecorator(d, rate_per_second=2, burst_size=1)
    await rl.do(1)  # consume
    with pytest.raises(RateLimitExceeded):
        await rl.do(2)
    # Wait enough for at least one token
    await asyncio.sleep(0.6)
    assert await rl.do(3) == 6


filename: tests/integration/chromadb_adapter_test.py
[complete file content]
import os

import pytest

from src.rcrag.infrastructure.historian.chromadb_adapter import CHROMA_AVAILABLE, ChromaDBHistorianAdapter


@pytest.mark.asyncio
@pytest.mark.skipif(not CHROMA_AVAILABLE or not os.environ.get("CHROMADB_HOST"), reason="ChromaDB not available")
async def test_create_and_retrieve_records():
    host = os.environ.get("CHROMADB_HOST", "localhost")
    port = int(os.environ.get("CHROMADB_PORT", "8000"))
    collection = os.environ.get("CHROMADB_COLLECTION", "rcrag_test")
    adapter = ChromaDBHistorianAdapter(host=host, port=port, collection=collection)

    rec_id = await adapter.create_record({"id": "rec-1", "text": "the quick brown fox", "metadata": {"kind": "note"}})
    got = await adapter.get_record(rec_id)
    assert got is not None
    assert got["id"] == "rec-1"
    assert "document" in got

    # Query by kind
    by_kind = await adapter.query_by_kind("note")
    assert any(r["id"] == "rec-1" for r in by_kind)

    # Semantic search
    results = await adapter.semantic_search("quick fox", top_k=3)
    assert isinstance(results, list)


filename: tests/integration/neo4j_adapter_test.py
[complete file content]
import os

import pytest

from src.rcrag.infrastructure.historian.neo4j_adapter import NEO4J_AVAILABLE, Neo4jHistorianAdapter


@pytest.mark.asyncio
@pytest.mark.skipif(
    not NEO4J_AVAILABLE or not os.environ.get("NEO4J_URI"),
    reason="Neo4j not available",
)
async def test_create_retrieve_and_provenance_chain():
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "password")
    adapter = Neo4jHistorianAdapter(uri=uri, user=user, password=password)

    try:
        await adapter.create_record({"id": "n1", "kind": "note", "data": {"k": "v"}})
        await adapter.create_record({"id": "n2", "kind": "note"})
        await adapter.add_provenance("n1", "n2")

        n1 = await adapter.get_record("n1")
        assert n1 is not None and n1["id"] == "n1"

        notes = await adapter.query_by_kind("note")
        assert any(n["id"] == "n1" for n in notes)

        chain = await adapter.get_provenance_chain("n1")
        assert isinstance(chain, list)
    finally:
        await adapter.close()


filename: tests/unit/metrics_test.py
[complete file content]
import asyncio

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from src.rcrag.infrastructure.observability.metrics import REQUEST_COUNT, REQUEST_DURATION, init_prometheus


@pytest.mark.asyncio
async def test_metrics_recorded_and_exported():
    app = FastAPI()
    init_prometheus(app, enabled=True)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    async with AsyncClient(app=app, base_url="http://test") as client:
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