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
