filename: src/rcrag/domain/models.py
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class Evidence:
    """Represents a piece of evidence used to support a record."""
    source_id: str
    weight: float = 1.0
    description: Optional[str] = None


@dataclass
class HistorianRecord:
    """Immutable record stored in the Historian."""
    id: Optional[str] = None
    kind: str = "generic"
    content: str = ""
    provenance_ids: List[str] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


filename: src/rcrag/domain/ports/historian_port.py
from abc import ABC, abstractmethod
from typing import List, Optional
from ..models import HistorianRecord


class HistorianPort(ABC):
    """Port for Historian implementations (ports-and-adapters pattern)."""

    @abstractmethod
    async def create_record(self, record: HistorianRecord) -> str:
        """Create a new immutable record. Returns the record ID."""
        pass

    @abstractmethod
    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        """Retrieve a record by ID."""
        pass

    @abstractmethod
    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        """Query records by kind."""
        pass

    @abstractmethod
    async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]:
        """Find all records that reference a source_id in provenance_ids."""
        pass


filename: src/rcrag/infrastructure/historian/decorators.py
import asyncio
import logging
import random
import time
from typing import List, Optional, Tuple, Type

from ...domain.models import HistorianRecord
from ...domain.ports.historian_port import HistorianPort


class HistorianDecorator(HistorianPort):
    """Base decorator for HistorianPort."""

    def __init__(self, inner: HistorianPort):
        self._inner = inner

    async def create_record(self, record: HistorianRecord) -> str:
        return await self._inner.create_record(record)

    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        return await self._inner.get_record(record_id)

    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        return await self._inner.query_by_kind(kind, limit=limit)

    async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]:
        return await self._inner.query_by_provenance(source_id)


class TimeoutDecorator(HistorianDecorator):
    """Applies a timeout to HistorianPort operations."""

    def __init__(self, inner: HistorianPort, timeout_seconds: float):
        super().__init__(inner)
        self._timeout = timeout_seconds

    async def create_record(self, record: HistorianRecord) -> str:
        return await asyncio.wait_for(super().create_record(record), timeout=self._timeout)

    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        return await asyncio.wait_for(super().get_record(record_id), timeout=self._timeout)

    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        return await asyncio.wait_for(super().query_by_kind(kind, limit=limit), timeout=self._timeout)

    async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]:
        return await asyncio.wait_for(super().query_by_provenance(source_id), timeout=self._timeout)


class RetryDecorator(HistorianDecorator):
    """Retries HistorianPort operations with exponential backoff and jitter."""

    def __init__(
        self,
        inner: HistorianPort,
        retries: int = 3,
        base_delay: float = 0.1,
        max_delay: float = 2.0,
        retry_exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    ):
        super().__init__(inner)
        self._retries = max(0, retries)
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._retry_exceptions = retry_exceptions

    async def _with_retry(self, coro_factory):
        attempt = 0
        while True:
            try:
                return await coro_factory()
            except self._retry_exceptions as e:
                if attempt >= self._retries:
                    raise
                # exponential backoff with full jitter
                delay = min(self._max_delay, self._base_delay * (2 ** attempt))
                delay = random.uniform(0, delay)
                await asyncio.sleep(delay)
                attempt += 1

    async def create_record(self, record: HistorianRecord) -> str:
        return await self._with_retry(lambda: super().create_record(record))

    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        return await self._with_retry(lambda: super().get_record(record_id))

    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        return await self._with_retry(lambda: super().query_by_kind(kind, limit=limit))

    async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]:
        return await self._with_retry(lambda: super().query_by_provenance(source_id))


class LoggingDecorator(HistorianDecorator):
    """Logs HistorianPort operations with duration and outcome."""

    def __init__(self, inner: HistorianPort, logger: Optional[logging.Logger] = None):
        super().__init__(inner)
        self._log = logger or logging.getLogger("rcrag.historian")

    async def _log_call(self, method: str, func):
        start = time.perf_counter()
        try:
            result = await func()
            duration_ms = (time.perf_counter() - start) * 1000.0
            self._log.info(
                "historian.call",
                extra={
                    "method": method,
                    "success": True,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000.0
            self._log.warning(
                "historian.call",
                extra={
                    "method": method,
                    "success": False,
                    "duration_ms": round(duration_ms, 2),
                    "error": repr(e),
                },
            )
            raise

    async def create_record(self, record: HistorianRecord) -> str:
        return await self._log_call("create_record", lambda: super().create_record(record))

    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        return await self._log_call("get_record", lambda: super().get_record(record_id))

    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        return await self._log_call("query_by_kind", lambda: super().query_by_kind(kind, limit=limit))

    async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]:
        return await self._log_call("query_by_provenance", lambda: super().query_by_provenance(source_id))


filename: src/rcrag/infrastructure/historian/inmemory_adapter.py
import asyncio
import uuid
from typing import Dict, List, Optional

from ...domain.models import HistorianRecord
from ...domain.ports.historian_port import HistorianPort


class InMemoryHistorianAdapter(HistorianPort):
    """In-memory adapter with async-safe state using asyncio.Lock."""

    def __init__(self):
        self._store: Dict[str, HistorianRecord] = {}
        self._lock = asyncio.Lock()

    async def create_record(self, record: HistorianRecord) -> str:
        async with self._lock:
            rec_id = record.id or uuid.uuid4().hex
            # ensure id is set on stored record
            record.id = rec_id
            self._store[rec_id] = record
            return rec_id

    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        async with self._lock:
            return self._store.get(record_id)

    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        async with self._lock:
            results = [r for r in self._store.values() if r.kind == kind]
            # sort by created_at desc if available
            results.sort(key=lambda r: getattr(r, "created_at", None), reverse=True)
            return results[: max(0, limit)]

    async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]:
        async with self._lock:
            return [r for r in self._store.values() if source_id in (r.provenance_ids or [])]


filename: src/rcrag/infrastructure/historian/mock_adapter.py
from typing import List, Optional

from ...domain.models import Evidence, HistorianRecord
from ...domain.ports.historian_port import HistorianPort
from .inmemory_adapter import InMemoryHistorianAdapter


class MockHistorianAdapter(HistorianPort):
    """Mock adapter backed by InMemory, pre-seeded with fake data for testing."""

    def __init__(self):
        self._inner = InMemoryHistorianAdapter()
        # pre-seed data
        # source records
        src1 = HistorianRecord(
            kind="source",
            content="Source document alpha",
            provenance_ids=[],
            evidence=[Evidence(source_id="seed", weight=0.9)],
            metadata={"title": "Alpha"},
        )
        src2 = HistorianRecord(
            kind="source",
            content="Source document beta",
            provenance_ids=[],
            evidence=[Evidence(source_id="seed", weight=0.8)],
            metadata={"title": "Beta"},
        )
        # note records referencing sources
        note1 = HistorianRecord(
            kind="note",
            content="Note derived from alpha",
            provenance_ids=[],
            evidence=[Evidence(source_id="alpha", weight=0.7)],
        )
        note2 = HistorianRecord(
            kind="note",
            content="Cross-referenced note from alpha and beta",
            provenance_ids=[],
            evidence=[Evidence(source_id="alpha", weight=0.8), Evidence(source_id="beta", weight=0.6)],
        )
        # persist them
        # Because create_record is async, but we're in sync __init__, call through loop via private method
        # To avoid event loop issues during import, we stage data after construction using synchronous approach:
        # We'll use our inner store directly because it's a simple in-memory dict and lock.
        # However, to keep the adapter contract consistent, we'll use inner's storage directly.
        for rec in (src1, src2, note1, note2):
            # direct access: self._inner._store is safe here before concurrency begins.
            rec_id = rec.id or rec.metadata.get("title") or rec.content.replace(" ", "-")
            rec.id = rec_id
            self._inner._store[rec_id] = rec

    async def create_record(self, record: HistorianRecord) -> str:
        return await self._inner.create_record(record)

    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        return await self._inner.get_record(record_id)

    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        return await self._inner.query_by_kind(kind, limit=limit)

    async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]:
        return await self._inner.query_by_provenance(source_id)


filename: src/rcrag/application/trust_policy.py
from typing import Iterable, List, Optional, Tuple

from ..domain.models import HistorianRecord


class TrustPolicy:
    """Computes trust scores and filters context based on a threshold."""

    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold

    def compute_trust_score(self, record: HistorianRecord) -> float:
        # Evidence-driven score with provenance bonus
        if record.evidence:
            weights = [max(0.0, min(1.0, ev.weight)) for ev in record.evidence]
            avg = sum(weights) / len(weights)
        else:
            avg = 0.5
        provenance_bonus = min(0.2, 0.05 * len(record.provenance_ids or []))
        score = min(1.0, max(0.0, 0.2 + 0.8 * avg + provenance_bonus))
        return score

    def filter_context(self, records: Iterable[HistorianRecord], threshold: Optional=float) -> List[HistorianRecord]:
        cut = self.threshold if threshold is None else threshold
        scored: List[Tuple[HistorianRecord, float]] = [(r, self.compute_trust_score(r)) for r in records]
        filtered = [r for r, s in scored if s >= cut]
        filtered.sort(key=lambda r: self.compute_trust_score(r), reverse=True)
        return filtered


filename: src/rcrag/application/rcrag_service.py
from typing import List, Tuple

from ..domain.models import HistorianRecord
from ..domain.ports.historian_port import HistorianPort
from .trust_policy import TrustPolicy


class RcragService:
    """Application service orchestrating historian queries and applying trust policy."""

    def __init__(self, historian: HistorianPort, trust_policy: TrustPolicy):
        self._historian = historian
        self._trust = trust_policy

    async def query(self, query: str, top_k: int = 3) -> List[HistorianRecord]:
        # Very simple heuristic to determine kind
        q = (query or "").lower()
        if q.startswith("kind:"):
            kind = q.split(":", 1)[1].strip() or "note"
        elif "source" in q:
            kind = "source"
        else:
            kind = "note"

        candidates = await self._historian.query_by_kind(kind, limit=max(10, top_k * 3))
        if not candidates:
            return []

        # Score all
        scored: List[Tuple[HistorianRecord, float]] = [(r, self._trust.compute_trust_score(r)) for r in candidates]
        # Filter by threshold
        above = [(r, s) for r, s in scored if s >= self._trust.threshold]
        # Choose best
        choose_from = above if above else scored
        choose_from.sort(key=lambda rs: rs[1], reverse=True)
        return [r for r, _ in choose_from[:top_k]]


filename: src/rcrag/infrastructure/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    historian_adapter: str = "inmemory"  # mock|inmemory
    historian_timeout_s: float = 5.0
    historian_retries: int = 3
    historian_logging: bool = True
    trust_threshold: float = 0.85
    top_k_default: int = 3

    class Config:
        env_file = ".env"


filename: src/rcrag/infrastructure/factory.py
import logging

from ..application.rcrag_service import RcragService
from ..application.trust_policy import TrustPolicy
from ..domain.ports.historian_port import HistorianPort
from .config import Settings
from .historian.decorators import LoggingDecorator, RetryDecorator, TimeoutDecorator
from .historian.inmemory_adapter import InMemoryHistorianAdapter
from .historian.mock_adapter import MockHistorianAdapter


def build_historian(cfg: Settings) -> HistorianPort:
    """Build historian with decorators based on config."""
    # Select adapter
    adapter_name = (cfg.historian_adapter or "").lower()
    if adapter_name == "mock":
        historian: HistorianPort = MockHistorianAdapter()
    elif adapter_name == "inmemory":
        historian = InMemoryHistorianAdapter()
    else:
        raise ValueError(f"Unknown historian adapter: {cfg.historian_adapter}")

    # Wrap with decorators: Timeout -> Retry -> Logging (outermost)
    if cfg.historian_timeout_s and cfg.historian_timeout_s > 0:
        historian = TimeoutDecorator(historian, timeout_seconds=cfg.historian_timeout_s)
    if cfg.historian_retries and cfg.historian_retries > 0:
        historian = RetryDecorator(historian, retries=cfg.historian_retries)
    if cfg.historian_logging:
        logger = logging.getLogger("rcrag.historian")
        historian = LoggingDecorator(historian, logger=logger)
    return historian


def build_services(cfg: Settings):
    """Build application services."""
    historian = build_historian(cfg)
    trust_policy = TrustPolicy(threshold=cfg.trust_threshold)
    rcrag_service = RcragService(historian, trust_policy)
    return rcrag_service


filename: src/main.py
from dataclasses import asdict
from fastapi import FastAPI
from rcrag.infrastructure.config import Settings
from rcrag.infrastructure.factory import build_services

app = FastAPI(title="RCRAG Service")
settings = Settings()
services = build_services(settings)


@app.post("/rcrag/query")
async def rcrag_query(query: str, top_k: int = None):
    """Query the Historian and return verified context."""
    if top_k is None:
        top_k = settings.top_k_default
    results = await services.query(query, top_k)
    return {
        "query": query,
        "results": [asdict(r) for r in results],
        "trust_policy_applied": True,
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "historian": settings.historian_adapter}


filename: tests/contract/historian_port_contract_test.py
import pytest

from rcrag.domain.models import Evidence, HistorianRecord
from rcrag.infrastructure.historian.inmemory_adapter import InMemoryHistorianAdapter
from rcrag.infrastructure.historian.mock_adapter import MockHistorianAdapter


@pytest.mark.parametrize("adapter_class", [InMemoryHistorianAdapter, MockHistorianAdapter])
@pytest.mark.asyncio
async def test_create_and_get_record(adapter_class):
    """Contract test: all adapters must support create and get."""
    adapter = adapter_class()
    record = HistorianRecord(
        kind="note",
        content="Test record",
        provenance_ids=["src-1"],
        evidence=[Evidence(source_id="src-1", weight=0.9)],
        metadata={"k": "v"},
    )
    rec_id = await adapter.create_record(record)
    fetched = await adapter.get_record(rec_id)
    assert fetched is not None
    assert fetched.id == rec_id
    assert fetched.kind == record.kind
    assert fetched.content == record.content
    assert fetched.provenance_ids == record.provenance_ids
    assert len(fetched.evidence) == len(record.evidence)


@pytest.mark.parametrize("adapter_class", [InMemoryHistorianAdapter, MockHistorianAdapter])
@pytest.mark.asyncio
async def test_query_by_kind(adapter_class):
    """Contract test: query_by_kind returns correct records."""
    adapter = adapter_class()
    # create records of different kinds
    r1 = HistorianRecord(kind="alpha", content="a1")
    r2 = HistorianRecord(kind="alpha", content="a2")
    r3 = HistorianRecord(kind="beta", content="b1")
    await adapter.create_record(r1)
    await adapter.create_record(r2)
    await adapter.create_record(r3)

    alpha = await adapter.query_by_kind("alpha", limit=10)
    kinds = {r.kind for r in alpha}
    assert kinds == {"alpha"}
    assert len(alpha) >= 2

    beta = await adapter.query_by_kind("beta", limit=10)
    kinds = {r.kind for r in beta}
    assert kinds == {"beta"}
    assert any(r.content == "b1" for r in beta)


@pytest.mark.parametrize("adapter_class", [InMemoryHistorianAdapter, MockHistorianAdapter])
@pytest.mark.asyncio
async def test_query_by_provenance(adapter_class):
    """Contract test: query_by_provenance returns referencing records."""
    adapter = adapter_class()
    base = HistorianRecord(kind="source", content="source-x")
    base_id = await adapter.create_record(base)
    ref1 = HistorianRecord(kind="note", content="refers-1", provenance_ids=[base_id])
    ref2 = HistorianRecord(kind="note", content="refers-2", provenance_ids=[base_id, "other"])
    ref3 = HistorianRecord(kind="note", content="no-ref")
    await adapter.create_record(ref1)
    await adapter.create_record(ref2)
    await adapter.create_record(ref3)

    results = await adapter.query_by_provenance(base_id)
    contents = {r.content for r in results}
    assert "refers-1" in contents
    assert "refers-2" in contents
    assert "no-ref" not in contents


filename: tests/unit/decorators_test.py
import asyncio
import logging
from typing import List, Optional

import pytest

from rcrag.domain.models import HistorianRecord
from rcrag.domain.ports.historian_port import HistorianPort
from rcrag.infrastructure.historian.decorators import LoggingDecorator, RetryDecorator, TimeoutDecorator


class FlakyAdapter(HistorianPort):
    """Adapter that fails N times before succeeding for get and query."""

    def __init__(self, fail_times: int = 2, delay: float = 0.0):
        self.fail_times = fail_times
        self.calls = 0
        self.delay = delay
        self._store = {}

    async def create_record(self, record: HistorianRecord) -> str:
        self._store["1"] = record
        return "1"

    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        await asyncio.sleep(self.delay)
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("temporary")
        return self._store.get("1")

    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        await asyncio.sleep(self.delay)
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("temporary")
        return [r for r in self._store.values() if r.kind == kind][:limit]

    async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]:
        return []


class SlowAdapter(HistorianPort):
    def __init__(self, sleep: float = 1.0):
        self.sleep = sleep

    async def create_record(self, record: HistorianRecord) -> str:
        await asyncio.sleep(self.sleep)
        return "x"

    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        await asyncio.sleep(self.sleep)
        return None

    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        await asyncio.sleep(self.sleep)
        return []

    async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]:
        await asyncio.sleep(self.sleep)
        return []


@pytest.mark.asyncio
async def test_retry_decorator_retries_and_succeeds():
    inner = FlakyAdapter(fail_times=2, delay=0.0)
    wrapped = RetryDecorator(inner, retries=3, base_delay=0.01, max_delay=0.05)
    rec = HistorianRecord(kind="k", content="v")
    await wrapped.create_record(rec)
    # Should succeed after retries
    result = await wrapped.get_record("1")
    assert result is not None
    assert inner.calls >= 3  # 2 failures + 1 success


@pytest.mark.asyncio
async def test_timeout_decorator_times_out():
    inner = SlowAdapter(sleep=0.2)
    wrapped = TimeoutDecorator(inner, timeout_seconds=0.05)
    with pytest.raises(asyncio.TimeoutError):
        await wrapped.get_record("any")


@pytest.mark.asyncio
async def test_logging_decorator_logs_success(caplog):
    caplog.set_level(logging.INFO, logger="rcrag.historian")
    inner = FlakyAdapter(fail_times=0)
    wrapped = LoggingDecorator(inner)
    rec = HistorianRecord(kind="x", content="y")
    await wrapped.create_record(rec)
    _ = await wrapped.get_record("1")
    events = [record.message for record in caplog.records]
    assert any("historian.call" in m for m in events)


filename: tests/application/rcrag_service_test.py
import pytest

from rcrag.application.rcrag_service import RcragService
from rcrag.application.trust_policy import TrustPolicy
from rcrag.domain.models import Evidence, HistorianRecord
from rcrag.infrastructure.historian.inmemory_adapter import InMemoryHistorianAdapter


@pytest.mark.asyncio
async def test_rcrag_service_filters_by_trust_threshold():
    historian = InMemoryHistorianAdapter()
    trust = TrustPolicy(threshold=0.8)
    service = RcragService(historian, trust)

    low = HistorianRecord(kind="note", content="low", evidence=[Evidence(source_id="a", weight=0.2)])
    mid = HistorianRecord(kind="note", content="mid", evidence=[Evidence(source_id="b", weight=0.6)])
    high = HistorianRecord(kind="note", content="high", evidence=[Evidence(source_id="c", weight=0.95)])

    await historian.create_record(low)
    await historian.create_record(mid)
    await historian.create_record(high)

    results = await service.query("some query", top_k=5)
    # Only the higher trust records should remain (depending on the TrustPolicy calculation)
    contents = [r.content for r in results]
    assert "high" in contents
    # "low" may be filtered out
    assert "low" not in contents


@pytest.mark.asyncio
async def test_rcrag_service_respects_top_k():
    historian = InMemoryHistorianAdapter()
    trust = TrustPolicy(threshold=0.0)  # allow all
    service = RcragService(historian, trust)

    for i in range(10):
        await historian.create_record(HistorianRecord(kind="note", content=f"rec-{i}"))

    results = await service.query("anything", top_k=3)
    assert len(results) == 3


filename: tests/integration/main_route_test.py
import importlib
import os

from fastapi.testclient import TestClient


def test_main_route_query_with_mock_adapter():
    # Ensure mock adapter is used (pre-seeded data)
    os.environ["HISTORIAN_ADAPTER"] = "mock"
    # Reload module to re-evaluate settings
    import src.main as main  # type: ignore
    importlib.reload(main)

    client = TestClient(main.app)
    resp = client.post("/rcrag/query", params={"query": "source documents", "top_k": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["trust_policy_applied"] is True
    assert "results" in data
    assert len(data["results"]) <= 2
    # Results should be JSON-serializable dicts
    assert isinstance(data["results"], list)
    if data["results"]:
        assert isinstance(data["results"][0], dict)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["historian"] == "mock"