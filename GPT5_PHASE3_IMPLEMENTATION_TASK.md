# Task for GPT-5: Implement Phase 3 - Production Hardening and Observability

## Context

Phases 1 and 2 are complete with all tests passing. The RCRAG service has:
- Ports-and-adapters architecture
- Resilience decorators (Timeout, Retry, Logging, Circuit Breaker)
- Application services (Trust Policy, Lifecycle Policy, RCRAG Service)
- Health endpoints, audit logging, CLI tool
- 19/19 tests passing

Now we're implementing **Phase 3** to add production-grade observability and performance features.

## Your Mission

Implement the complete Phase 3 features for production readiness. Provide all the code files needed.

## Phase 3 Requirements

### 1. OpenTelemetry Tracing
**File:** `src/rcrag/infrastructure/observability/tracing.py`

- Configure OpenTelemetry SDK
- Instrument FastAPI automatically
- Instrument all decorators (add spans)
- Instrument historian operations
- Export to OTLP endpoint (configurable)
- Include trace context in logs

### 2. Prometheus Metrics
**File:** `src/rcrag/infrastructure/observability/metrics.py`

- Prometheus client integration
- Metrics to track:
  - Request duration histogram (by endpoint)
  - Request count counter (by endpoint, status)
  - Circuit breaker state gauge (closed=0, open=1, half_open=2)
  - Historian operation duration histogram
  - Error count counter (by type)
- `/metrics` endpoint for Prometheus scraping

### 3. Cache Decorator
**File:** `src/rcrag/infrastructure/historian/cache_decorator.py`

- In-memory cache for read operations
- TTL (time-to-live) support
- LRU eviction policy
- Cache hit/miss metrics
- Configurable cache size
- Only caches `get_record` and `query_*` methods
- Inherits from `HistorianDecorator`

### 4. Rate Limit Decorator
**File:** `src/rcrag/infrastructure/historian/rate_limit_decorator.py`

- Token bucket algorithm
- Configurable rate (requests per second)
- Configurable burst size
- Raises `RateLimitExceeded` exception when limit hit
- Metrics for rate limit hits
- Inherits from `HistorianDecorator`

### 5. Real Historian Adapters

**File:** `src/rcrag/infrastructure/historian/chromadb_adapter.py`
- Implements `HistorianPort` using ChromaDB
- Semantic search via embeddings
- Stores records as documents with metadata
- Configurable collection name
- Async operations

**File:** `src/rcrag/infrastructure/historian/neo4j_adapter.py`
- Implements `HistorianPort` using Neo4j
- Stores records as nodes
- Provenance as relationships (edges)
- Cypher queries for provenance chains
- Async operations via neo4j driver

### 6. Update Configuration
**Updates:** `src/rcrag/infrastructure/config.py`

Add settings for:
- OpenTelemetry: `otel_enabled`, `otel_exporter_endpoint`, `otel_service_name`
- Prometheus: `prometheus_enabled`
- Cache: `cache_enabled`, `cache_ttl_seconds`, `cache_max_size`
- Rate limit: `rate_limit_enabled`, `rate_limit_requests_per_second`, `rate_limit_burst_size`
- ChromaDB: `chromadb_host`, `chromadb_port`, `chromadb_collection`
- Neo4j: `neo4j_uri`, `neo4j_user`, `neo4j_password`

### 7. Update Factory
**Updates:** `src/rcrag/infrastructure/factory.py`

- Add cache decorator to stack (if enabled)
- Add rate limit decorator to stack (if enabled)
- Support ChromaDB and Neo4j adapters based on `historian_adapter` setting
- Initialize OpenTelemetry if enabled
- Initialize Prometheus if enabled

### 8. Update main.py
**Updates:** `src/main.py`

- Add `/metrics` endpoint (if Prometheus enabled)
- Initialize OpenTelemetry tracing
- Add trace context to all requests

## Tests to Write

### 1. Cache Decorator Tests
**File:** `tests/unit/cache_decorator_test.py`

- Test cache hit returns cached value
- Test cache miss calls underlying adapter
- Test TTL expiration
- Test LRU eviction
- Test cache metrics

### 2. Rate Limit Decorator Tests
**File:** `tests/unit/rate_limit_decorator_test.py`

- Test requests within limit succeed
- Test requests exceeding limit raise exception
- Test burst capacity
- Test token bucket refill over time

### 3. ChromaDB Adapter Tests
**File:** `tests/integration/chromadb_adapter_test.py`

- Test create and retrieve records
- Test semantic search
- Test query by kind
- Requires ChromaDB running (or mock)

### 4. Neo4j Adapter Tests
**File:** `tests/integration/neo4j_adapter_test.py`

- Test create and retrieve records
- Test provenance chain queries
- Requires Neo4j running (or mock)

### 5. Metrics Tests
**File:** `tests/unit/metrics_test.py`

- Test metrics are recorded
- Test Prometheus export format

## Deliverable Format

Please provide **complete, working code** for all files using this format:

```
filename: path/to/file.py
[complete file content]
```

Make sure:
- ✅ All imports are correct (use `from src.rcrag.` not `from rcrag.`)
- ✅ All endpoints are `async def` (not `def`)
- ✅ Use Pydantic v2 syntax (`from pydantic_settings import BaseSettings`)
- ✅ Code follows Phase 1 and 2 patterns
- ✅ Tests are comprehensive
- ✅ Configuration is extensible
- ✅ Documentation is clear

Generate the complete Phase 3 implementation now.
