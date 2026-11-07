from fastapi.testclient import TestClient


def test_health_ok_without_reachable_db():
    from app.main import app

    with TestClient(app) as client:
        body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["db"] == "disconnected"
