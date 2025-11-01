import os

import pytest

from src.rcrag.infrastructure.historian.neo4j_adapter import NEO4J_AVAILABLE, Neo4jHistorianAdapter


@pytest.mark.asyncio
@pytest.mark.skipif(
    not NEO4J_AVAILABLE or not os.environ.get("NEO4J_URI"),
    reason="Neo4j not available",
)
async def test_create_retrieve_and_provenance_chain():
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "password")
    adapter = Neo4jHistorianAdapter(uri=uri, user=user, password=password)

    try:
        await adapter.create_record({"id": "n1", "kind": "note", "data": {"k": "v"}})
        await adapter.create_record({"id": "n2", "kind": "note"})
        await adapter.add_provenance("n1", "n2")

        n1 = await adapter.get_record("n1")
        assert n1 is not None and n1["id"] == "n1"

        notes = await adapter.query_by_kind("note")
        assert any(n["id"] == "n1" for n in notes)

        chain = await adapter.get_provenance_chain("n1")
        assert isinstance(chain, list)
    finally:
        await adapter.close()
