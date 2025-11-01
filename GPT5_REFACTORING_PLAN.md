Refactoring Plan: Elevate RCRAG Historian Layer to Ports-and-Adapters with Resilience, Observability, and Contract Safety

1) Executive summary of the gaps
- Boundary/architecture gaps
  - No clear ports-and-adapters separation. FastAPI route reaches into a concrete mock and calls a method not defined in the port (search), creating interface drift.
  - Cross-cutting concerns (timeouts, retries, circuit breakers, logging, metrics) are missing or inlined into endpoints.
  - Trust policy is hardcoded in the route; no application-layer orchestration service.
  - No factory/configuration system to compose adapters and decorators for different environments.
- Model/validation gaps
  - Domain models are dataclasses with strings for IDs/timestamps; no API boundary schemas or serializers.
  - Lifecycle validation exists conceptually, but not as reusable domain policy with enforced state transitions.
- Async/resilience/observability gaps
  - In-memory adapter has async event loop issues.
  - No retries, timeouts, circuit breakers, or backoff strategies.
  - No metrics, audit logs, health checks, or structured logging.
- Testing gaps
  - No contract test suite to prevent drift between Mock and InMemory or future adapters.
  - No property-based tests for lifecycle policies or query semantics.
- Search/hybrid retrieval gaps
  - Hybrid search not formalized. Domain-layer merge/rerank absent. Search invoked from a mock, not through a port.

Highest-priority improvements
- Stabilize the port: define a canonical HistorianPort and align adapters to it. Move search orchestration into an application service.
- Introduce decorator-based resilience (timeout, retry) and logging around the Historian port.
- Add a contract test suite for the Historian port to lock behavior and prevent mock drift.
- Introduce a configuration/factory system to assemble adapters and decorators per environment.
- Fix in-memory async issues.

Keep vs refactor
- Keep: core dataclasses (as domain models), basic HistorianClient interface (rename to HistorianPort, add minimal missing ops), lifecycle validation concept, FastAPI.
- Refactor: adapter method names to match the port, remove route-level trust policy in favor of application service, add decorators and factory, implement robust InMemory adapter, add Pydantic API schemas, introduce tests and observability.

2) Phased refactoring roadmap
Phase 1: Stabilize the core and boundaries
- Define domain ports and application services. Align existing adapters to the port and wrap with timeout/retry/logging decorators.
- Create a configuration/factory to build the historian stack for dev/test/prod.
- Move trust policy into an application-level RcragService. Expose FastAPI endpoints via the service.
- Fix InMemory adapter async issues.
- Add initial contract tests.

Phase 2: Expand resilience, testing, and developer ergonomics
- Add circuit breaker, metrics, audit logs, correlation IDs, and health checks.
- Introduce Pydantic request/response schemas at API boundary; keep dataclasses in domain.
- Add CLI and seed scripts. Add a simple hybrid search service in the application layer with a pluggable SearchPort (term + optional embedding).
- Implement lifecycle policy enforcement as a domain service.

Phase 3: Production hardening and observability
- Full OpenTelemetry tracing and Prometheus metrics; structured logs with audit events.
- Caching and optional rate limiting decorators.
- External Historian adapters (e.g., HTTP/gRPC) and a vector index adapter.
- Domain-level reranker; feature flags; typed timestamps and ULIDs; configuration hardening and dashboards.

3) Concrete implementation tasks (by phase)

Phase 1: Stabilize core and boundaries
Files to create/modify
- src/rcrag/domain/models.py
  - Move Evidence and HistorianRecord here (keep dataclasses). Consider using datetime for timestamp internally with a serializer at the boundary; keep string for now to avoid breaking changes.
- src/rcrag/domain/ports/historian_port.py
  - Rename HistorianClient to HistorianPort; methods:
    - create_record(record: HistorianRecord) -> str
    - get_record(record_id: str) -> Optional[HistorianRecord]
    - query_by_kind(kind: str, limit: int = 10) -> List[HistorianRecord]
    - query_by_provenance(source_id: str) -> List[HistorianRecord]
  - Do not expose search here; search will be an application service that composes historian queries and optional SearchPort later.
- src/rcrag/infrastructure/historian/inmemory_adapter.py
  - Adapt from existing InMemoryHistorianClient to implement HistorianPort with correct async usage:
    - Use asyncio.Lock for state.
    - Avoid creating or closing event loops in methods.
    - Ensure methods are pure async without blocking calls.
- src/rcrag/infrastructure/historian/mock_adapter.py
  - Update MockHistorianClient to implement HistorianPort methods only. Remove non-port methods (like search). Provide fake data for tests.
- src/rcrag/infrastructure/historian/decorators.py
  - Base decorator: class HistorianDecorator(HistorianPort)
  - TimeoutDecorator: asyncio.wait_for
  - RetryDecorator: simple exponential backoff with jitter
  - LoggingDecorator: structured logs for method calls and durations
- src/rcrag/application/trust_policy.py
  - Implement compute_trust_score(record) and filter_context(records, threshold)
- src/rcrag/application/rcrag_service.py
  - RcragService with method query(query: str, top_k: int) -> List[HistorianRecord]
  - For Phase 1, implement naive search using historian.query_by_kind("fact") and simple keyword matching on subject/summary/body, then apply trust policy. This replaces the route-level logic.
- src/rcrag/infrastructure/config.py
  - Pydantic BaseSettings for selecting adapter (mock|inmemory), decorator options (timeouts, retries), thresholds, etc.
- src/rcrag/infrastructure/factory.py
  - build_historian(cfg): instantiate adapter and wrap with decorators as configured
  - build_services(cfg): return RcragService wired with historian
- src/main.py
  - Replace direct MockHistorianClient usage with factory-built service.
  - Add FastAPI dependency wiring.

Code patterns and examples
- Decorator base and timeout decorator
  - Example:
    class HistorianDecorator(HistorianPort):
        def __init__(self, inner: HistorianPort):
            self.inner = inner

        async def create_record(self, record):
            return await self.inner.create_record(record)
        # other methods delegate

    class TimeoutDecorator(HistorianDecorator):
        def __init__(self, inner: HistorianPort, timeout_s: float):
            super().__init__(inner)
            self.timeout_s = timeout_s

        async def create_record(self, record):
            return await asyncio.wait_for(self.inner.create_record(record), timeout=self.timeout_s)

        async def get_record(self, record_id):
            return await asyncio.wait_for(self.inner.get_record(record_id), timeout=self.timeout_s)

        async def query_by_kind(self, kind, limit=10):
            return await asyncio.wait_for(self.inner.query_by_kind(kind, limit), timeout=self.timeout_s)

        async def query_by_provenance(self, source_id):
            return await asyncio.wait_for(self.inner.query_by_provenance(source_id), timeout=self.timeout_s)
- Retry decorator
    class RetryDecorator(HistorianDecorator):
        def __init__(self, inner, max_attempts=3, base_backoff=0.05, max_backoff=0.5):
            super().__init__(inner)
            self.max_attempts = max_attempts
            self.base_backoff = base_backoff
            self.max_backoff = max_backoff

        async def _with_retry(self, func, *args, **kwargs):
            attempt = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    attempt += 1
                    if attempt >= self.max_attempts:
                        raise
                    delay = min(self.base_backoff * (2 ** (attempt - 1)), self.max_backoff)
                    delay = delay * (0.5 + random.random())  # jitter
                    await asyncio.sleep(delay)

        async def create_record(self, record):
            return await self._with_retry(self.inner.create_record, record)

        # duplicate pattern for other methods
- Logging decorator
    class LoggingDecorator(HistorianDecorator):
        async def create_record(self, record):
            start = time.perf_counter()
            try:
                result = await self.inner.create_record(record)
                return result
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                logger.info("historian.create_record", extra={"duration_ms": duration_ms})

- Factory
    def build_historian(cfg) -> HistorianPort:
        if cfg.historian_adapter == "mock":
            base = MockHistorianAdapter()
        else:
            base = InMemoryHistorianAdapter()
        wrapped = base
        if cfg.historian_timeout_s:
            wrapped = TimeoutDecorator(wrapped, cfg.historian_timeout_s)
        if cfg.historian_retries > 0:
            wrapped = RetryDecorator(wrapped, cfg.historian_retries)
        if cfg.historian_logging:
            wrapped = LoggingDecorator(wrapped)
        return wrapped

- Application service
    class RcragService:
        def __init__(self, historian: HistorianPort, trust_policy: TrustPolicy):
            self.historian = historian
            self.trust = trust_policy

        async def query(self, query: str, top_k: int = 3):
            candidates = await self.historian.query_by_kind("fact", limit=200)
            scored = [(self.trust.compute_trust_score(r), r) for r in candidates if self._matches(r, query)]
            scored.sort(key=lambda x: x[0], reverse=True)
            selected = [r for _, r in scored[:top_k]]
            return selected

        def _matches(self, r, query):
            q = query.lower()
            hay = " ".join([r.subject, r.summary, r.body_md]).lower()
            return q in hay

Tests to write
- tests/contract/historian_port_contract_test.py
  - Parameterize over adapters (Mock, InMemory)
  - CRUD and query behavior equivalence, including edge cases and ordering semantics
- tests/unit/decorators_test.py
  - Timeout fires, retries backoff, logging called
- tests/application/rcrag_service_test.py
  - Trust policy applied; deterministic top_k selection; handles empty results
- tests/integration/main_route_test.py
  - /rcrag/query returns expected structure; trust_policy_applied flag preserved

Configuration to add
- rcrag/infrastructure/config.py
  - class Settings(BaseSettings): historian_adapter, historian_timeout_s, historian_retries, historian_logging, trust_threshold, top_k_default
  - Load from env/.env

Phase 2: Expand resilience, testing, and developer ergonomics
Files to create/modify
- src/rcrag/infrastructure/historian/circuit_breaker_decorator.py
  - Simple circuit breaker with states: closed, open, half_open. Configurable failure threshold and reset timeout.
- src/rcrag/infrastructure/observability/health.py
  - Health/readiness endpoints. Readiness pings historian via a lightweight call (e.g., query_by_kind with limit=1).
- src/rcrag/infrastructure/logging.py
  - Configure structured logging (JSON), correlation IDs, request logging middleware.
- src/rcrag/application/policies.py
  - LifecyclePolicy: validate and enforce transitions proposal → execution_report → fact and status changes.
- src/rcrag/application/search_service.py
  - Introduce SearchPort interface and a BasicSearchService that does:
    - term filtering over historian records
    - optional embedding-based similarity if a VectorSearchPort is provided (stub in Phase 2)
  - Merge and rerank at this layer; keep HistorianPort oblivious.
- src/rcrag/api/schemas.py
  - Pydantic schemas for request/response; conversion adapters to/from domain dataclasses.
- src/rcrag/cli.py
  - Typer-based CLI to seed records, run queries, check health.
- src/main.py
  - Add /health/live and /health/ready endpoints
  - Use Pydantic schemas in the /rcrag/query endpoint
- src/rcrag/infrastructure/audit.py
  - Audit logger that emits decisions: query, selected record IDs, trust scores, policy version, correlation ID.

Tests to write
- Contract tests extended with lifecycle validation scenarios.
- Property-based tests for lifecycle transitions (Hypothesis).
- Health endpoints tests under degraded adapters (use a failing stub).
- Audit logs presence and schema validity.
- Circuit breaker behavior tests (open, half-open recovery).

Configuration to add
- Circuit breaker config: failure_threshold, reset_timeout_s, half_open_max_calls
- Observability config: enable_audit, log_level, otel_exporter_url (Phase 3), prometheus_enabled
- Trust policy config: threshold, policy version id (for audit)

Phase 3: Production hardening and observability
Files to create/modify
- src/rcrag/infrastructure/observability/tracing.py
  - OpenTelemetry setup; instrument FastAPI and decorators.
- src/rcrag/infrastructure/observability/metrics.py
  - Prometheus metrics: request durations, error counts, circuit breaker state.
- src/rcrag/infrastructure/cache_decorator.py
  - Optional in-memory cache for read methods of HistorianPort with TTL.
- src/rcrag/infrastructure/rate_limit_decorator.py
  - Simple token-bucket rate limiter to protect downstream historian.
- src/rcrag/infrastructure/historian/http_adapter.py
  - Example external historian adapter (HTTP). Reuse decorators for resilience.
- src/rcrag/infrastructure/vector/vector_port.py and inmemory_vector_adapter.py
  - Vector index port and an in-memory or simple FAISS-like stub.
- src/rcrag/application/rerank.py
  - Domain-layer reranking function that merges lexical and vector scores, configurable weights.
- Data model improvements
  - Introduce ULID/UUID provider port and typed timestamps internally; serializers at API boundary so external behavior remains stable.
- Dashboard and alerts
  - Provide Grafana dashboard JSON and alert rules (documented, stored in repo ops/ folder).

Tests to write
- Load tests and latency SLO checks for /rcrag/query under simulated failures (circuit breaker trips).
- Tracing/metrics presence tests (smoke).
- Cache correctness tests (consistency, TTL expiry).

Configuration to add
- Feature flags: enable_vector_search, enable_caching, enable_rate_limit
- IDs: id_provider = "ulid" | "uuid"
- SLO targets for alerts documentation

4) Migration strategy
- Non-breaking, incremental refactor
  - Keep current endpoints and response fields. Replace internals with service composition. Preserve “trust_policy_applied” response flag.
  - Implement MockHistorianAdapter.search compatibility temporarily inside RcragService; deprecate direct adapter.search usage.
- Adapter alignment
  - Update Mock and InMemory to the new HistorianPort in a single PR; keep thin compatibility wrapper around old names if necessary during transition.
- Tests as safety net
  - Add contract tests first against existing adapters; use them to guide refactor.
- Feature flags and config
  - Roll in decorators with conservative defaults (timeouts enabled, retries low).
  - Introduce circuit breaker disabled by default; enable in staging, then production.
- Risk/effort tradeoff
  - Phase 1 is medium effort, high safety gain. It addresses async bugs and interface drift.
  - Phase 2 adds resilience and developer tools with moderate complexity.
  - Phase 3 is higher effort but optional for initial external integrations. Do after teams adopt Phase 1/2.

5) Alignment with Sovereign Core Philosophy
- Emergence through process
  - The plan builds capabilities iteratively: domain-first ports, then resilience and tests, then observability and external adapters. Each phase produces working value and learning.
- Dual-Layer Architecture (Inside/Outside)
  - Inside: domain models and policies remain pure dataclasses; ports define the domain’s needs.
  - Outside: adapters, decorators, observability, and config are externalized and swappable. Search is an application-layer orchestration that composes ports.
- Eye Cannot See the Eye
  - Observability (audit logs, tracing, metrics) and contract tests give the system introspection into its own behavior. The trust policy is explicit, versioned, and auditable. Decorators emit telemetry at the boundaries, making hidden dynamics visible.

6) Code examples for key patterns
- FastAPI wiring to application service
  - Example:
    app = FastAPI(title="RCRAG Service")
    settings = Settings()  # loads env
    historian = build_historian(settings)
    trust = TrustPolicy(threshold=settings.trust_threshold, version=settings.trust_policy_version)
    rcrag = RcragService(historian, trust)

    class QueryRequest(BaseModel):
        query: str
        top_k: int = 3

    class RecordSchema(BaseModel):
        id: str
        timestamp: str
        actor_id: str
        actor_type: str
        kind: str
        subject: str
        summary: str
        body_md: str
        provenance_ids: List[str] = []
        status: str = "pending"
        tags: List[str] = []
        metadata: Dict[str, Any] = {}

    @app.post("/rcrag/query")
    async def rcrag_query(req: QueryRequest):
        records = await rcrag.query(req.query, req.top_k)
        payload = [RecordSchema(**asdict(r)) for r in records]
        return {"query": req.query, "context": payload, "trust_policy_applied": True}

- Lifecycle policy usage
    class LifecyclePolicy:
        allowed = {
            ("proposal", "execution_report"),
            ("execution_report", "fact"),
        }
        def can_transition(self, from_kind: str, to_kind: str) -> bool:
            return (from_kind, to_kind) in self.allowed

        def validate_record(self, record: HistorianRecord):
            # Example: facts must reference an execution_report provenance
            if record.kind == "fact":
                assert any("execution_report" in pid for pid in record.provenance_ids), "Fact must derive from execution_report"

7) Testing strategy
- Contract tests
  - Define a shared test suite for HistorianPort: CRUD semantics, immutability (create returns ID, records don’t change), query behaviors, provenance linkage, and edge conditions.
  - Run the suite against all adapters (Mock, InMemory, later HTTP).
- Unit tests
  - Decorators: retry/timeout behavior, logging/audit emissions.
  - Trust policy: score computation and thresholding.
  - Lifecycle policy: valid/invalid transitions.
- Integration tests
  - FastAPI endpoints: schema validation, error handling, health checks.
  - RcragService with adapter stack and feature flags.
- Property-based tests
  - Lifecycle transitions over random sequences; ensure invariants hold.
- Resilience/chaos tests
  - Adapter stub that fails intermittently to validate retry and circuit breaker behaviors.
- Performance smoke
  - Simple latency budget checks for /rcrag/query with small datasets.

Summary of initial concrete action items (Phase 1)
- Create domain ports and move models under domain.
- Align Mock and InMemory adapters to HistorianPort; fix async issues.
- Implement timeout, retry, and logging decorators; add configuration and factory.
- Create RcragService and TrustPolicy; move route logic out of main.py.
- Introduce Pydantic API schemas for requests/responses.
- Establish contract test suite and run it against both adapters.
- Wire health endpoints stub and basic structured logging.

This plan moves you from a working prototype to a testable, observable, and resilient architecture without breaking current functionality, while setting the stage for hybrid search, external integrations, and production readiness.