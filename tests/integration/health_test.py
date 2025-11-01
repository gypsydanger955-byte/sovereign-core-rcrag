from fastapi.testclient import TestClient

from main import app


class HealthyHistorian:
    def ping(self):
        return True


class UnhealthyHistorian:
    def ping(self):
        raise RuntimeError("down")


def test_health_live_ok():
    client = TestClient(app)
    res = client.get("/health/live")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"


def test_health_ready_ok():
    app.state.historian = HealthyHistorian()
    client = TestClient(app)
    res = client.get("/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"


def test_health_ready_503_on_failure():
    app.state.historian = UnhealthyHistorian()
    client = TestClient(app)
    res = client.get("/health/ready")
    assert res.status_code == 503
    data = res.json()
    assert data["status"] == "not_ready"
