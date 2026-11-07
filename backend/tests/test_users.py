import pytest
from bson import ObjectId


def make_user(client, **overrides):
    body = {"name": "Ayşe", "main_language": "tr", "consent": True, **overrides}
    return client.post("/users", json=body)


def test_create_user_saves_defaults(client, fake_db):
    res = make_user(client)
    assert res.status_code == 201
    user_id = res.json()["user_id"]

    import asyncio

    doc = asyncio.run(fake_db.users.find_one({"_id": ObjectId(user_id)}))
    assert doc["name"] == "Ayşe"
    assert doc["main_language"] == "tr"
    assert doc["threshold"] == 0.80
    assert doc["consent"] is True
    assert doc["created_at"] is not None


def test_get_user_returns_saved_user(client):
    user_id = make_user(client, name="  Can  ", main_language="EN").json()["user_id"]
    res = client.get(f"/users/{user_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["user_id"] == user_id
    assert body["name"] == "Can"  # trimmed
    assert body["main_language"] == "en"  # lower-cased
    assert body["threshold"] == 0.80


def test_mixed_language_allowed(client):
    assert make_user(client, main_language="both").status_code == 201


def test_consent_required(client):
    res = make_user(client, consent=False)
    assert res.status_code == 400
    assert "Consent" in res.json()["detail"]


@pytest.mark.parametrize("bad", [{"name": "   "}, {"name": ""}, {"main_language": "xx"}])
def test_invalid_input_rejected(client, bad):
    assert make_user(client, **bad).status_code == 422


@pytest.mark.parametrize("user_id", ["not-an-id", str(ObjectId())])
def test_unknown_user_is_404(client, user_id):
    assert client.get(f"/users/{user_id}").status_code == 404


def test_no_database_gives_503():
    from fastapi.testclient import TestClient

    from app.main import app

    res = TestClient(app).post("/users", json={"name": "A", "main_language": "tr", "consent": True})
    assert res.status_code == 503
