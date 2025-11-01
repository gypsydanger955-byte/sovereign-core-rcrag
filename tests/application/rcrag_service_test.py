import pytest

from src.rcrag.application.rcrag_service import RcragService
from src.rcrag.application.trust_policy import TrustPolicy
from src.rcrag.domain.models import Evidence, HistorianRecord
from src.rcrag.infrastructure.historian.inmemory_adapter import InMemoryHistorianAdapter


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
