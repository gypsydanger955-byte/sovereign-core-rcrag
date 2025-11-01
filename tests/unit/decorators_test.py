import asyncio
import logging
from typing import Any, Dict, List, Optional

import pytest

from src.rcrag.domain.models import HistorianRecord
from src.rcrag.domain.ports.historian_port import HistorianPort
from src.rcrag.infrastructure.historian.decorators import LoggingDecorator, RetryDecorator, TimeoutDecorator


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

    async def search(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[HistorianRecord]:
        await asyncio.sleep(self.delay)
        return []

    async def query_records(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[HistorianRecord]:
        await asyncio.sleep(self.delay)
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

    async def search(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[HistorianRecord]:
        await asyncio.sleep(self.sleep)
        return []

    async def query_records(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[HistorianRecord]:
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
