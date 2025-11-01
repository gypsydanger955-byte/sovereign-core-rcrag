import os

import pytest

from src.rcrag.infrastructure.historian.chromadb_adapter import CHROMA_AVAILABLE, ChromaDBHistorianAdapter


@pytest.mark.asyncio
@pytest.mark.skipif(not CHROMA_AVAILABLE or not os.environ.get("CHROMADB_HOST"), reason="ChromaDB not available")
async def test_create_and_retrieve_records():
    host = os.environ.get("CHROMADB_HOST", "localhost")
    port = int(os.environ.get("CHROMADB_PORT", "8000"))
    collection = os.environ.get("CHROMADB_COLLECTION", "rcrag_test")
    adapter = ChromaDBHistorianAdapter(host=host, port=port, collection=collection)

    rec_id = await adapter.create_record({"id": "rec-1", "text": "the quick brown fox", "metadata": {"kind": "note"}})
    got = await adapter.get_record(rec_id)
    assert got is not None
    assert got["id"] == "rec-1"
    assert "document" in got

    # Query by kind
    by_kind = await adapter.query_by_kind("note")
    assert any(r["id"] == "rec-1" for r in by_kind)

    # Semantic search
    results = await adapter.semantic_search("quick fox", top_k=3)
    assert isinstance(results, list)
