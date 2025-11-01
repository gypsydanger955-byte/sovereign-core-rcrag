import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional, Tuple, Type

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

    async def search(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[HistorianRecord]:
        return await self._inner.search(query, filters, limit)

    async def query_records(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[HistorianRecord]:
        return await self._inner.query_records(filters, limit)


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

    async def search(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[HistorianRecord]:
        return await asyncio.wait_for(super().search(query, filters, limit), timeout=self._timeout)

    async def query_records(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[HistorianRecord]:
        return await asyncio.wait_for(super().query_records(filters, limit), timeout=self._timeout)


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
        return await self._with_retry(lambda: self._inner.create_record(record))

    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        return await self._with_retry(lambda: self._inner.get_record(record_id))

    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        return await self._with_retry(lambda: self._inner.query_by_kind(kind, limit=limit))

    async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]:
        return await self._with_retry(lambda: self._inner.query_by_provenance(source_id))

    async def search(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[HistorianRecord]:
        return await self._with_retry(lambda: self._inner.search(query, filters, limit))

    async def query_records(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[HistorianRecord]:
        return await self._with_retry(lambda: self._inner.query_records(filters, limit))


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
        return await self._log_call("create_record", lambda: self._inner.create_record(record))

    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        return await self._log_call("get_record", lambda: self._inner.get_record(record_id))

    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        return await self._log_call("query_by_kind", lambda: self._inner.query_by_kind(kind, limit=limit))

    async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]:
        return await self._log_call("query_by_provenance", lambda: self._inner.query_by_provenance(source_id))

    async def search(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[HistorianRecord]:
        return await self._log_call("search", lambda: self._inner.search(query, filters, limit))

    async def query_records(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[HistorianRecord]:
        return await self._log_call("query_records", lambda: self._inner.query_records(filters, limit))
