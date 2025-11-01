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
