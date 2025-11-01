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
