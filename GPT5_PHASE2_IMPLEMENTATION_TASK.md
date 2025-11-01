# Task for GPT-5: Implement Phase 2 - Resilience, Testing, and Developer Ergonomics

## Context

Phase 1 is complete and all tests are passing. The RCRAG service has a solid foundation with ports-and-adapters architecture, decorators, and contract tests.

Now we're implementing **Phase 2** to add:
1. Circuit breaker for resilience
2. Health/readiness endpoints
3. Structured logging and audit logs
4. Lifecycle policy enforcement
5. Basic hybrid search service
6. Pydantic API schemas
7. CLI for developer ergonomics

## Your Mission

Implement the complete Phase 2 features. Provide all the code files needed.

## Phase 2 Requirements

### 1. Circuit Breaker Decorator
**File:** `src/rcrag/infrastructure/historian/circuit_breaker_decorator.py`

- States: `closed`, `open`, `half_open`
- Configurable failure threshold (e.g., 5 failures → open)
- Configurable reset timeout (e.g., 30 seconds)
- Half-open allows limited calls to test recovery
- Inherits from `HistorianDecorator`

### 2. Health Endpoints
**File:** `src/rcrag/infrastructure/observability/health.py`

- `check_liveness()`: Always returns healthy (service is running)
- `check_readiness(historian: HistorianPort)`: Tests historian with lightweight query
- Used by `/health/live` and `/health/ready` endpoints in FastAPI

### 3. Structured Logging
**File:** `src/rcrag/infrastructure/logging.py`

- Configure JSON structured logging
- Add correlation IDs to all log entries
- Request logging middleware for FastAPI
- Log levels configurable via Settings

### 4. Audit Logger
**File:** `src/rcrag/infrastructure/audit.py`

- `AuditLogger` class that emits structured audit events
- Records: query, selected record IDs, trust scores, policy version, correlation ID
- Used by `RcragService` to log all queries

### 5. Lifecycle Policy
**File:** `src/rcrag/application/policies.py`

- `LifecyclePolicy` class
- Validates state transitions: `proposal` → `execution_report` → `fact`
- Validates status changes: `pending` → `active` → `superseded`/`disputed`/`rejected`
- Raises exceptions for invalid transitions

### 6. Search Service
**File:** `src/rcrag/application/search_service.py`

- `SearchPort` interface (for future vector search)
- `BasicSearchService` that does:
  - Term filtering over historian records
  - Keyword matching on subject/summary/body
  - Merge and rerank results
  - Stub for embedding-based search (Phase 3)

### 7. API Schemas
**File:** `src/rcrag/api/schemas.py`

- Pydantic request/response schemas
- `QueryRequest`, `QueryResponse`, `HistorianRecordSchema`
- Conversion functions to/from domain dataclasses

### 8. CLI Tool
**File:** `src/rcrag/cli.py`

- Typer-based CLI
- Commands:
  - `rcrag seed`: Seed test records into historian
  - `rcrag query <text>`: Run a query
  - `rcrag health`: Check service health
- Uses the same factory/config as the service

### 9. Update main.py
**Updates:** `src/main.py`

- Add `/health/live` and `/health/ready` endpoints
- Use Pydantic schemas in `/rcrag/query`
- Add request logging middleware
- Wire in audit logger

### 10. Update Config
**Updates:** `src/rcrag/infrastructure/config.py`

Add settings for:
- Circuit breaker: `circuit_breaker_enabled`, `circuit_breaker_failure_threshold`, `circuit_breaker_reset_timeout_s`
- Audit: `enable_audit`, `audit_log_file`
- Logging: `log_level`, `log_format` (json|text)

### 11. Update Factory
**Updates:** `src/rcrag/infrastructure/factory.py`

- Add circuit breaker decorator to historian stack (if enabled)
- Wire audit logger into RcragService
- Configure structured logging

## Tests to Write

### 1. Circuit Breaker Tests
**File:** `tests/unit/circuit_breaker_test.py`

- Test state transitions (closed → open → half_open → closed)
- Test failure threshold triggers open state
- Test reset timeout allows half_open
- Test half_open recovery

### 2. Health Endpoint Tests
**File:** `tests/integration/health_test.py`

- Test `/health/live` always returns 200
- Test `/health/ready` returns 200 when historian is healthy
- Test `/health/ready` returns 503 when historian fails

### 3. Lifecycle Policy Tests
**File:** `tests/application/lifecycle_policy_test.py`

- Test valid transitions succeed
- Test invalid transitions raise exceptions
- Property-based tests with Hypothesis (optional)

### 4. Audit Logger Tests
**File:** `tests/unit/audit_test.py`

- Test audit events are emitted
- Test audit log schema is valid
- Test correlation IDs are included

## Deliverable Format

Please provide **complete, working code** for all files using this format:

```filename: path/to/file.py
[complete file content]
```

Make sure:
- ✅ All imports are correct
- ✅ Code follows Phase 1 patterns (decorators, factory, etc.)
- ✅ Tests are comprehensive
- ✅ Configuration is extensible
- ✅ Documentation is clear

Generate the complete Phase 2 implementation now.
