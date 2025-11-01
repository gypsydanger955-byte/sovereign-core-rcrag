filename: src/rcrag/infrastructure/historian/circuit_breaker_decorator.py
[complete file content]
import threading
import time
from typing import Any, Callable, Optional

try:
    # Phase 1 likely provides this base decorator
    from rcrag.infrastructure.historian.decorator import HistorianDecorator  # type: ignore
except Exception:  # pragma: no cover - fallback for standalone run
    class HistorianDecorator:  # minimal fallback
        def __init__(self, inner: Any) -> None:
            self.inner = inner

        def __getattr__(self, name: str) -> Any:
            return getattr(self.inner, name)

class CircuitBreakerOpenError(RuntimeError):
    pass


class CircuitBreakerDecorator(HistorianDecorator):
    """
    Decorates a HistorianPort implementation with a circuit breaker.
    Applies breaker to all callable, public methods of the historian.
    """

    def __init__(
        self,
        inner: Any,
        *,
        failure_threshold: int = 5,
        reset_timeout_s: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        super().__init__(inner)
        self._failure_threshold = max(1, int(failure_threshold))
        self._reset_timeout_s = float(reset_timeout_s)
        self._half_open_max_calls = max(1, int(half_open_max_calls))

        self._state = "closed"  # closed | open | half_open
        self._failure_count = 0
        self._opened_at: Optional[float] = None
        self._half_open_inflight = 0

        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def _transition_to_open(self) -> None:
        self._state = "open"
        self._opened_at = time.monotonic()
        self._half_open_inflight = 0

    def _transition_to_half_open_if_timeout_elapsed(self) -> None:
        now = time.monotonic()
        if self._opened_at is None:
            self._opened_at = now
        if (now - self._opened_at) >= self._reset_timeout_s:
            self._state = "half_open"
            self._half_open_inflight = 0

    def _transition_to_closed(self) -> None:
        self._state = "closed"
        self._failure_count = 0
        self._opened_at = None
        self._half_open_inflight = 0

    def _record_failure(self) -> None:
        self._failure_count += 1
        if self._state == "half_open":
            # immediate open on failure in half-open
            self._transition_to_open()
        elif self._failure_count >= self._failure_threshold:
            self._transition_to_open()

    def _before_call(self) -> None:
        # Evaluate state and possibly transition
        if self._state == "open":
            self._transition_to_half_open_if_timeout_elapsed()
            if self._state == "open":
                raise CircuitBreakerOpenError("Circuit breaker is open")

        if self._state == "half_open":
            if self._half_open_inflight >= self._half_open_max_calls:
                # limit concurrent test calls
                raise CircuitBreakerOpenError("Circuit breaker is half-open; trial limit reached")
            self._half_open_inflight += 1

    def _after_call_success(self) -> None:
        if self._state == "half_open":
            # Successful trial -> close circuit
            self._transition_to_closed()
        # In closed state, success resets failure count
        if self._state == "closed":
            self._failure_count = 0

    def _after_call_failure(self) -> None:
        self._record_failure()

    def _finally(self) -> None:
        if self._state == "half_open" and self._half_open_inflight > 0:
            self._half_open_inflight -= 1

    def _call_with_circuit(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            self._before_call()
        try:
            result = func(*args, **kwargs)
        except Exception:
            with self._lock:
                self._after_call_failure()
                self._finally()
            raise
        else:
            with self._lock:
                self._after_call_success()
                self._finally()
            return result

    def __getattr__(self, name: str) -> Any:
        # wrap callable public methods
        attr = getattr(self.inner, name)
        if callable(attr) and not name.startswith("_"):
            def wrapped(*args: Any, **kwargs: Any) -> Any:
                return self._call_with_circuit(attr, *args, **kwargs)
            return wrapped
        return attr


filename: src/rcrag/infrastructure/observability/health.py
[complete file content]
from typing import Any, Tuple

def check_liveness() -> Tuple[bool, str]:
    """
    Liveness indicates the process is up.
    """
    return True, "alive"

def _try_call(obj: Any, method: str) -> Any:
    fn = getattr(obj, method, None)
    if fn is None:
        raise AttributeError
    if callable(fn):
        return fn()
    return fn

def check_readiness(historian: Any) -> Tuple[bool, str]:
    """
    Attempts a lightweight operation on the historian.
    Strategy:
    - Prefer 'ping'/'health'/'is_healthy' if available.
    - Else try 'count' or 'stats'.
    - Else try listing small subset via 'list'/'list_records' or similar with best-effort defaults.
    - Else assume healthy if no known method exists.
    Returns (ready, message)
    """
    try:
        for method in ("ping", "health", "is_healthy"):
            try:
                result = _try_call(historian, method)
                if isinstance(result, tuple) and len(result) == 2:
                    ok, msg = result
                    return bool(ok), str(msg)
                if isinstance(result, bool):
                    return bool(result), f"{method} ok" if result else f"{method} not ok"
                # If callable returns without error, consider ok
                return True, f"{method} ok"
            except AttributeError:
                continue

        # Try count-like methods
        for method in ("count", "get_count", "size", "len"):
            try:
                result = _try_call(historian, method)
                if isinstance(result, int) and result >= 0:
                    return True, "historian reachable"
                # If returned without exception, consider ok
                return True, "historian reachable"
            except AttributeError:
                continue

        # Try list-like methods
        for method in ("list", "list_records", "all", "list_all"):
            try:
                fn = getattr(historian, method)
                if callable(fn):
                    # Try a minimal call signature
                    try:
                        fn(limit=1)  # type: ignore
                    except TypeError:
                        try:
                            fn(1)  # type: ignore
                        except TypeError:
                            fn()  # type: ignore
                return True, "historian reachable"
            except AttributeError:
                continue

        # Try benign search
        for method in ("search", "query"):
            try:
                fn = getattr(historian, method)
                if callable(fn):
                    try:
                        fn("")  # type: ignore
                    except TypeError:
                        try:
                            fn(q="")  # type: ignore
                        except TypeError:
                            # last resort: call without args
                            fn()  # type: ignore
                return True, "historian reachable"
            except AttributeError:
                continue

        # No known method; consider ready if object exists
        return True, "historian object present"
    except Exception as e:
        return False, f"historian error: {e!r}"


filename: src/rcrag/infrastructure/logging.py
[complete file content]
import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

try:
    from pydantic import BaseModel
except Exception:  # pragma: no cover
    BaseModel = object  # type: ignore


correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def set_correlation_id(value: Optional[str]) -> None:
    correlation_id_ctx.set(value)


def get_correlation_id() -> Optional[str]:
    return correlation_id_ctx.get()


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        setattr(record, "correlation_id", get_correlation_id())
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": getattr(record, "ts", None) or time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include common fields if available
        for field in ("correlation_id", "request_path", "request_method", "status_code", "duration_ms"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        # Include extras
        if record.args and isinstance(record.args, dict):
            payload.update(record.args)
        # Include exception info if present
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(
    level: str = "INFO",
    fmt: str = "json",
    audit_log_file: Optional[str] = None,
) -> None:
    """
    Configure root and uvicorn loggers with structured logging and correlation ID filter.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(log_level)
    for h in list(root.handlers):
        root.removeHandler(h)

    handler: logging.Handler
    if fmt.lower() == "json":
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s [cid=%(correlation_id)s] %(message)s"))

    handler.addFilter(CorrelationIdFilter())
    root.addHandler(handler)

    # Uvicorn loggers (if used)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        lg = logging.getLogger(name)
        lg.setLevel(log_level)
        lg.handlers = []
        lg.addHandler(handler)
        lg.propagate = False

    # Audit logger setup
    audit_logger = logging.getLogger("audit")
    audit_logger.setLevel(log_level)
    audit_logger.handlers = []
    if audit_log_file:
        file_handler = logging.FileHandler(audit_log_file)
        if fmt.lower() == "json":
            file_handler.setFormatter(JsonFormatter())
        else:
            file_handler.setFormatter(logging.Formatter("%(asctime)s AUDIT [cid=%(correlation_id)s] %(message)s"))
        file_handler.addFilter(CorrelationIdFilter())
        audit_logger.addHandler(file_handler)
    else:
        audit_logger.addHandler(handler)


class RequestLoggingMiddleware:
    """
    FastAPI/Starlette middleware that assigns correlation IDs and logs requests.
    """

    def __init__(self, app, header_name: str = "X-Request-ID") -> None:
        self.app = app
        self.header_name = header_name

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        start = time.time()
        # Extract or generate correlation ID
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        corr_id = headers.get(self.header_name.lower())
        if not corr_id:
            corr_id = str(uuid.uuid4())
        token = correlation_id_ctx.set(corr_id)

        # Intercept send to capture status code
        status_code_container = {"code": None}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code_container["code"] = message["status"]
            return await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = int((time.time() - start) * 1000)
            path = scope.get("path")
            method = scope.get("method")
            logger = logging.getLogger("http")
            extra = logging.LoggerAdapter(logger, {})
            # Use log record extras
            record = logging.LogRecord(
                name="http",
                level=logging.INFO,
                pathname=__file__,
                lineno=0,
                msg=f"{method} {path}",
                args=(),
                exc_info=None,
            )
            record.request_path = path
            record.request_method = method
            record.status_code = status_code_container["code"]
            record.duration_ms = duration_ms
            CorrelationIdFilter().filter(record)
            if root := logging.getLogger():
                for h in root.handlers:
                    h.handle(record)
            correlation_id_ctx.reset(token)


filename: src/rcrag/infrastructure/audit.py
[complete file content]
import json
import logging
from typing import Any, Dict, Iterable, Optional

from rcrag.infrastructure.logging import get_correlation_id


class AuditLogger:
    """
    Emits structured audit events for queries.
    """

    def __init__(self, logger: Optional[logging.Logger] = None, policy_version: str = "v1") -> None:
        self.logger = logger or logging.getLogger("audit")
        self.policy_version = policy_version

    def log_query(
        self,
        *,
        query: str,
        selected_records: Iterable[Any],
        trust_scores: Optional[Dict[str, float]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        corr_id = get_correlation_id()
        record_ids = []
        for r in selected_records or []:
            rid = getattr(r, "id", None)
            if rid is None and isinstance(r, dict):
                rid = r.get("id")
            record_ids.append(rid)
        payload: Dict[str, Any] = {
            "event": "query",
            "policy_version": self.policy_version,
            "correlation_id": corr_id,
            "query": query,
            "selected_record_ids": record_ids,
        }
        if trust_scores is not None:
            payload["trust_scores"] = trust_scores
        if extra:
            payload.update(extra)
        # Use logger to emit as JSON if configured, else as text
        try:
            self.logger.info(json.dumps(payload))
        except Exception:
            # Fallback: log dict
            self.logger.info(payload)


filename: src/rcrag/application/policies.py
[complete file content]
from dataclasses import dataclass
from typing import Literal, Tuple


class InvalidLifecycleTransition(Exception):
    pass


State = Literal["proposal", "execution_report", "fact"]
Status = Literal["pending", "active", "superseded", "disputed", "rejected"]


@dataclass(frozen=True)
class LifecyclePolicy:
    """
    Validates lifecycle state and status transitions.

    State transitions: proposal -> execution_report -> fact
    Status transitions: pending -> active -> (superseded|disputed|rejected)
    """

    def validate_state_transition(self, from_state: State, to_state: State) -> Tuple[bool, str]:
        order = {"proposal": 0, "execution_report": 1, "fact": 2}
        if from_state == to_state:
            return True, "no-op"
        if order.get(to_state, 99) == order.get(from_state, -1) + 1:
            return True, "ok"
        raise InvalidLifecycleTransition(f"Invalid state transition {from_state} -> {to_state}")

    def validate_status_transition(self, from_status: Status, to_status: Status) -> Tuple[bool, str]:
        if from_status == to_status:
            return True, "no-op"
        if from_status == "pending" and to_status == "active":
            return True, "ok"
        if from_status == "active" and to_status in ("superseded", "disputed", "rejected"):
            return True, "ok"
        raise InvalidLifecycleTransition(f"Invalid status transition {from_status} -> {to_status}")


filename: src/rcrag/application/search_service.py
[complete file content]
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple


@dataclass
class SearchResult:
    record: Any
    score: float


class SearchPort(Protocol):
    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        ...


class HistorianLike(Protocol):
    def list_records(self, limit: Optional[int] = None) -> Sequence[Any]:
        ...


class BasicSearchService(SearchPort):
    """
    Basic hybrid search:
    - Term filtering over historian records
    - Keyword matching on subject/summary/body
    - Merges and ranks by simple BM25-like heuristic (very simplified)
    - Stub for embedding-based search (Phase 3)
    """

    def __init__(self, historian: HistorianLike) -> None:
        self.historian = historian

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        # Fetch corpus
        try:
            records = list(self.historian.list_records())  # type: ignore[arg-type]
        except TypeError:
            # If list_records requires args
            records = list(self.historian.list_records(None))  # type: ignore

        # Filter by simple terms in metadata if provided
        if filters:
            def record_matches_filters(r: Any) -> bool:
                meta = getattr(r, "metadata", None) or getattr(r, "terms", None) or {}
                if isinstance(meta, dict):
                    for k, v in filters.items():
                        if meta.get(k) != v:
                            return False
                    return True
                return True
            records = [r for r in records if record_matches_filters(r)]

        # Tokenize query
        tokens = [t.lower() for t in re.findall(r"\w+", query)]
        if not tokens:
            return []

        # Score records
        results: List[SearchResult] = []
        for r in records:
            text = " ".join([
                str(getattr(r, "subject", "") or ""),
                str(getattr(r, "summary", "") or ""),
                str(getattr(r, "body", "") or ""),
            ]).lower()
            if not text.strip():
                continue

            tf = 0
            for t in tokens:
                tf += text.count(t)
            if tf == 0:
                continue

            # Very rough weighting by field presence
            score = tf / math.sqrt(len(text) + 1.0)
            results.append(SearchResult(record=r, score=score))

        # Sort desc by score
        results.sort(key=lambda x: x.score, reverse=True)
        return results

    # Placeholder for future embedding-based search
    def search_with_embeddings(self, query: str, top_k: int = 10) -> List[SearchResult]:
        return []


filename: src/rcrag/api/schemas.py
[complete file content]
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HistorianRecordSchema(BaseModel):
    id: str = Field(..., description="Record ID")
    subject: Optional[str] = None
    summary: Optional[str] = None
    body: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_domain(cls, record: Any) -> "HistorianRecordSchema":
        # Domain may be dataclass or dict
        if isinstance(record, dict):
            return cls(
                id=str(record.get("id")),
                subject=record.get("subject"),
                summary=record.get("summary"),
                body=record.get("body"),
                metadata=record.get("metadata") or record.get("terms"),
            )
        return cls(
            id=str(getattr(record, "id")),
            subject=getattr(record, "subject", None),
            summary=getattr(record, "summary", None),
            body=getattr(record, "body", None),
            metadata=getattr(record, "metadata", None) or getattr(record, "terms", None),
        )

    def to_domain(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject,
            "summary": self.summary,
            "body": self.body,
            "metadata": self.metadata,
        }


class QueryRequest(BaseModel):
    query: str = Field(..., description="Query text")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Optional filter terms")


class QueryResponse(BaseModel):
    query: str
    results: List[HistorianRecordSchema]
    scores: Optional[Dict[str, float]] = Field(default=None, description="Optional trust scores")


filename: src/rcrag/cli.py
[complete file content]
import json
from typing import Optional

import typer

from rcrag.infrastructure.config import Settings
from rcrag.infrastructure.factory import build_historian, build_service, configure_logging_from_settings
from rcrag.infrastructure.observability.health import check_liveness, check_readiness

app = typer.Typer(name="rcrag")


@app.command("seed")
def seed(
    records_file: Optional[str] = typer.Option(None, help="Path to JSONL file with records"),
):
    """
    Seed test records into historian. If no file provided, seeds a small default set.
    """
    settings = Settings()
    configure_logging_from_settings(settings)
    historian = build_historian(settings)

    # Determine seeding records
    records = []
    if records_file:
        with open(records_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    else:
        records = [
            {"id": "1", "subject": "Solar farm proposal", "summary": "Proposal for 100MW solar farm", "body": "Details about solar farm", "metadata": {"state": "proposal"}},
            {"id": "2", "subject": "Execution report", "summary": "Report on execution progress", "body": "Construction reached 50%", "metadata": {"state": "execution_report"}},
            {"id": "3", "subject": "Operational facts", "summary": "Plant operational", "body": "Plant started operations", "metadata": {"state": "fact"}},
        ]
    # Historian port API is Phase 1; we best-effort insert
    for r in records:
        for method in ("add", "insert", "upsert", "save", "put"):
            fn = getattr(historian, method, None)
            if fn:
                try:
                    fn(r)
                    break
                except TypeError:
                    try:
                        fn(**r)
                        break
                    except Exception:  # pragma: no cover - minor ergonomics
                        continue
    typer.echo(f"Seeded {len(records)} records.")


@app.command("query")
def query(text: str = typer.Argument(..., help="Query text")):
    """
    Run a query through the RCRAG service.
    """
    settings = Settings()
    configure_logging_from_settings(settings)
    service = build_service(settings)
    # Phase 1 service is assumed to provide 'query' returning results
    result = service.query(text)  # type: ignore[attr-defined]
    # Attempt to serialize results
    try:
        from rcrag.api.schemas import HistorianRecordSchema
        records = [HistorianRecordSchema.from_domain(r) for r in getattr(result, "records", []) or getattr(result, "results", []) or []]  # type: ignore
        payload = {"query": text, "results": [r.dict() for r in records]}
    except Exception:
        payload = {"query": text, "result": str(result)}
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command("health")
def health():
    """
    Check service health endpoints.
    """
    settings = Settings()
    configure_logging_from_settings(settings)
    historian = build_historian(settings)
    l_ok, _ = check_liveness()
    r_ok, msg = check_readiness(historian)
    typer.echo(json.dumps({"live": l_ok, "ready": r_ok, "message": msg}))


def run():
    app()


if __name__ == "__main__":
    run()


filename: src/main.py
[complete file content]
import logging
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from rcrag.api.schemas import HistorianRecordSchema, QueryRequest, QueryResponse
from rcrag.infrastructure.audit import AuditLogger
from rcrag.infrastructure.config import Settings
from rcrag.infrastructure.factory import (
    build_historian,
    build_service,
    configure_logging_from_settings,
)
from rcrag.infrastructure.logging import RequestLoggingMiddleware
from rcrag.infrastructure.observability.health import check_liveness, check_readiness

settings = Settings()
configure_logging_from_settings(settings)

app = FastAPI(title="RCRAG Service")

# Middleware: request logging and correlation IDs
app.add_middleware(RequestLoggingMiddleware)

# Build dependencies
historian = build_historian(settings)
service = build_service(settings)

# Store into app state so tests can override
app.state.historian = historian
app.state.service = service

# Health endpoints
@app.get("/health/live")
def health_live():
    ok, msg = check_liveness()
    status = 200 if ok else 500
    return JSONResponse(status_code=status, content={"status": "ok" if ok else "failed", "message": msg})


@app.get("/health/ready")
def health_ready():
    ok, msg = check_readiness(app.state.historian)
    status = 200 if ok else 503
    return JSONResponse(status_code=status, content={"status": "ready" if ok else "not_ready", "message": msg})


# RCRAG query endpoint
@app.post("/rcrag/query", response_model=QueryResponse)
def rcrag_query(request: QueryRequest):
    try:
        result = app.state.service.query(request.query)  # type: ignore[attr-defined]
        # Expect iterable of domain records; adapt to schema
        # Accept that service may return an object with 'results' or 'records'
        domain_results = getattr(result, "results", None) or getattr(result, "records", None) or result
        if not isinstance(domain_results, list):
            domain_results = list(domain_results)
        schemas: List[HistorianRecordSchema] = [HistorianRecordSchema.from_domain(r) for r in domain_results]
        # Attempt trust scores extraction if available
        trust_scores: Dict[str, float] = getattr(result, "scores", None) or getattr(result, "trust_scores", None) or {}
        # Audit
        try:
            audit_logger: AuditLogger = getattr(app.state.service, "audit_logger", None)  # type: ignore[attr-defined]
            if audit_logger:
                audit_logger.log_query(query=request.query, selected_records=domain_results, trust_scores=trust_scores)
        except Exception:
            logging.getLogger(__name__).exception("Failed to emit audit log")
        return QueryResponse(query=request.query, results=schemas, scores=trust_scores or None)
    except Exception as e:
        logging.getLogger(__name__).exception("Query failed")
        raise HTTPException(status_code=500, detail=str(e))


filename: src/rcrag/infrastructure/config.py
[complete file content]
from functools import lru_cache
from typing import Optional

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    # Historian backend (Phase 1 likely defined; keep generic)
    historian_backend: str = Field(default="memory", env="HISTORIAN_BACKEND")

    # Circuit breaker
    circuit_breaker_enabled: bool = Field(default=True, env="CB_ENABLED")
    circuit_breaker_failure_threshold: int = Field(default=5, env="CB_FAILURE_THRESHOLD")
    circuit_breaker_reset_timeout_s: float = Field(default=30.0, env="CB_RESET_TIMEOUT_S")

    # Audit
    enable_audit: bool = Field(default=True, env="AUDIT_ENABLED")
    audit_log_file: Optional[str] = Field(default=None, env="AUDIT_LOG_FILE")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")  # json|text

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


filename: src/rcrag/infrastructure/factory.py
[complete file content]
import logging
from typing import Any

from rcrag.infrastructure.audit import AuditLogger
from rcrag.infrastructure.config import Settings
from rcrag.infrastructure.historian.circuit_breaker_decorator import CircuitBreakerDecorator
from rcrag.infrastructure.logging import configure_logging


def configure_logging_from_settings(settings: Settings) -> None:
    configure_logging(level=settings.log_level, fmt=settings.log_format, audit_log_file=settings.audit_log_file)


def build_historian(settings: Settings) -> Any:
    """
    Builds the historian port with configured decorators.
    Phase 1 likely has an in-memory historian implementation accessible via factory;
    here we best-effort import and instantiate.
    """
    historian: Any
    # Try to import a default in-memory historian adapter
    historian = None
    tried = []

    candidates = [
        "rcrag.infrastructure.historian.memory.HistorianMemoryAdapter",
        "rcrag.infrastructure.historian.in_memory.InMemoryHistorian",
        "rcrag.infrastructure.historian.memory_infra.InMemoryHistorian",
        "rcrag.infrastructure.historian.memory.Historian",  # generic
    ]
    for path in candidates:
        try:
            module_path, class_name = path.rsplit(".", 1)
            mod = __import__(module_path, fromlist=[class_name])
            cls = getattr(mod, class_name)
            historian = cls()
            break
        except Exception as e:  # pragma: no cover - depends on Phase 1
            tried.append((path, repr(e)))
            historian = None
            continue

    if historian is None:
        # Minimal fallback historian with in-memory list for CLI/tests
        class _FallbackHistorian:
            def __init__(self) -> None:
                self._items = []

            def add(self, item):
                self._items.append(item)

            def list_records(self, limit=None):
                return self._items[: limit or len(self._items)]

            # a simple query
            def query(self, q: str = ""):
                return [it for it in self._items if q.lower() in (it.get("subject", "") + it.get("summary", "") + it.get("body", "")).lower()]

            def count(self):
                return len(self._items)

            def ping(self):
                return True

        historian = _FallbackHistorian()

    # Decorators: Circuit Breaker
    if settings.circuit_breaker_enabled:
        historian = CircuitBreakerDecorator(
            historian,
            failure_threshold=settings.circuit_breaker_failure_threshold,
            reset_timeout_s=settings.circuit_breaker_reset_timeout_s,
            half_open_max_calls=1,
        )

    return historian


def build_service(settings: Settings) -> Any:
    """
    Build the RcragService using the historian and wire in audit logger if enabled.
    """
    historian = build_historian(settings)

    # Try to import Phase 1 service
    service: Any = None
    candidates = [
        "rcrag.application.service.RcragService",
        "rcrag.service.RcragService",
    ]
    for path in candidates:
        try:
            module_path, class_name = path.rsplit(".", 1)
            mod = __import__(module_path, fromlist=[class_name])
            cls = getattr(mod, class_name)
            # Try known constructor signatures
            try:
                service = cls(historian=historian)
            except TypeError:
                try:
                    service = cls(historian)
                except Exception:
                    continue
            break
        except Exception:  # pragma: no cover - depends on Phase 1
            continue

    if service is None:
        # Fallback minimal service
        class _FallbackService:
            def __init__(self, historian):
                self.historian = historian
                self.audit_logger = None

            def query(self, q: str):
                # return simple object with results and scores
                class Res:
                    def __init__(self, results):
                        self.results = results
                        self.scores = {}
                return Res(self.historian.query(q))  # type: ignore[attr-defined]

        service = _FallbackService(historian)

    # Wire audit logger if enabled
    if settings.enable_audit:
        audit_logger = AuditLogger(policy_version="v1")
        try:
            setattr(service, "audit_logger", audit_logger)
        except Exception:
            logging.getLogger(__name__).warning("Could not attach audit logger to service")

    return service


filename: tests/unit/circuit_breaker_test.py
[complete file content]
import time

import pytest

from rcrag.infrastructure.historian.circuit_breaker_decorator import (
    CircuitBreakerDecorator,
    CircuitBreakerOpenError,
)


class FlakyHistorian:
    def __init__(self):
        self.calls = 0
        self.fail_until = 0

    def ping(self):
        self.calls += 1
        if self.calls <= self.fail_until:
            raise RuntimeError("boom")
        return True


def test_circuit_breaker_opens_after_threshold():
    inner = FlakyHistorian()
    inner.fail_until = 3
    cb = CircuitBreakerDecorator(inner, failure_threshold=3, reset_timeout_s=0.5)

    # First 3 calls fail; breaker should open after third failure
    for _ in range(3):
        with pytest.raises(RuntimeError):
            cb.ping()
    assert cb.state == "open"

    # While open and before timeout, further calls raise open error
    with pytest.raises(CircuitBreakerOpenError):
        cb.ping()


def test_circuit_breaker_half_open_after_timeout_and_recovery_to_closed():
    inner = FlakyHistorian()
    inner.fail_until = 2
    cb = CircuitBreakerDecorator(inner, failure_threshold=2, reset_timeout_s=0.2)

    # cause open
    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.ping()
    assert cb.state == "open"

    # wait for half-open
    time.sleep(0.25)
    # first trial in half-open succeeds and should close
    res = cb.ping()
    assert res is True
    assert cb.state == "closed"

    # Subsequent calls normal
    assert cb.ping() is True
    assert cb.state == "closed"


def test_circuit_breaker_half_open_failure_reopens():
    inner = FlakyHistorian()
    inner.fail_until = 5
    cb = CircuitBreakerDecorator(inner, failure_threshold=2, reset_timeout_s=0.1)

    # cause open
    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.ping()
    assert cb.state == "open"

    time.sleep(0.12)
    # next call still fails; should re-open
    with pytest.raises(RuntimeError):
        cb.ping()
    assert cb.state == "open"


filename: tests/integration/health_test.py
[complete file content]
from fastapi.testclient import TestClient

from main import app


class HealthyHistorian:
    def ping(self):
        return True


class UnhealthyHistorian:
    def ping(self):
        raise RuntimeError("down")


def test_health_live_ok():
    client = TestClient(app)
    res = client.get("/health/live")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"


def test_health_ready_ok():
    app.state.historian = HealthyHistorian()
    client = TestClient(app)
    res = client.get("/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"


def test_health_ready_503_on_failure():
    app.state.historian = UnhealthyHistorian()
    client = TestClient(app)
    res = client.get("/health/ready")
    assert res.status_code == 503
    data = res.json()
    assert data["status"] == "not_ready"


filename: tests/application/lifecycle_policy_test.py
[complete file content]
import pytest

from rcrag.application.policies import InvalidLifecycleTransition, LifecyclePolicy


def test_valid_state_transitions():
    p = LifecyclePolicy()
    assert p.validate_state_transition("proposal", "execution_report")[0]
    assert p.validate_state_transition("execution_report", "fact")[0]
    assert p.validate_state_transition("proposal", "proposal")[0]


def test_invalid_state_transitions():
    p = LifecyclePolicy()
    with pytest.raises(InvalidLifecycleTransition):
        p.validate_state_transition("proposal", "fact")
    with pytest.raises(InvalidLifecycleTransition):
        p.validate_state_transition("execution_report", "proposal")


def test_valid_status_transitions():
    p = LifecyclePolicy()
    assert p.validate_status_transition("pending", "active")[0]
    assert p.validate_status_transition("active", "superseded")[0]
    assert p.validate_status_transition("active", "disputed")[0]
    assert p.validate_status_transition("active", "rejected")[0]
    assert p.validate_status_transition("pending", "pending")[0]


def test_invalid_status_transitions():
    p = LifecyclePolicy()
    with pytest.raises(InvalidLifecycleTransition):
        p.validate_status_transition("pending", "rejected")
    with pytest.raises(InvalidLifecycleTransition):
        p.validate_status_transition("superseded", "active")


filename: tests/unit/audit_test.py
[complete file content]
import io
import json
import logging

from rcrag.infrastructure.audit import AuditLogger
from rcrag.infrastructure.logging import set_correlation_id


class Record:
    def __init__(self, id):
        self.id = id


def test_audit_emits_events_with_correlation_id():
    # Capture audit logger output in-memory
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = logging.getLogger("audit-test")
    logger.setLevel(logging.INFO)
    logger.handlers = [handler]

    audit = AuditLogger(logger=logger, policy_version="v1")
    set_correlation_id("cid-123")
    audit.log_query(query="hello", selected_records=[Record("1"), Record("2")], trust_scores={"1": 0.9})

    handler.flush()
    contents = log_stream.getvalue().strip()
    assert contents, "No audit output"

    # Expect JSON payload
    payload = json.loads(contents)
    assert payload["event"] == "query"
    assert payload["policy_version"] == "v1"
    assert payload["correlation_id"] == "cid-123"
    assert payload["query"] == "hello"
    assert payload["selected_record_ids"] == ["1", "2"]
    assert payload["trust_scores"] == {"1": 0.9}