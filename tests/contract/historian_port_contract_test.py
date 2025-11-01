import pytest

from src.rcrag.domain.models import Evidence, HistorianRecord
from src.rcrag.infrastructure.historian.inmemory_adapter import InMemoryHistorianAdapter
from src.rcrag.infrastructure.historian.mock_adapter import MockHistorianAdapter


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
