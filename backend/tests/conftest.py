"""Shared test setup: fake keys so the app can be imported without a real backend/.env."""

import pytest

FAKE_ENV = {
    "ANTHROPIC_API_KEY": "test-anthropic",
    "GROQ_API_KEY": "test-groq",
    "OPENAI_API_KEY": "",
    "ELEVENLABS_API_KEY": "test-elevenlabs",
    "ELEVENLABS_VOICE_GIRL": "",  # child voices off unless a test switches them on
    "ELEVENLABS_VOICE_BOY": "",
    # Nothing listens here, so tests never touch a real database.
    "MONGODB_URI": "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=200",
    "MONGODB_DB": "echo_test",
    "EMBEDDING_API_KEY": "test-embedding",
    "FRONTEND_URL": "http://localhost:3000",
}


@pytest.fixture(autouse=True)
def fake_env(monkeypatch, tmp_path):
    for key, value in FAKE_ENV.items():
        monkeypatch.setenv(key, value)
    # Each test gets its own empty uploads folder, never the real one.
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def fake_db():
    """An in-memory MongoDB (mongomock) plugged into app.db for the duration of a test."""
    from mongomock_motor import AsyncMongoMockClient

    from app import db

    database = AsyncMongoMockClient(tz_aware=True)["echo_test"]
    db.set_db(database)
    yield database
    db.set_db(None)


@pytest.fixture
def client(fake_db):
    """API client backed by the in-memory database (startup is skipped, so no real DB)."""
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def user_id(client):
    """A freshly signed-up Turkish-speaking user."""
    res = client.post("/users", json={"name": "Ayşe", "main_language": "tr", "consent": True})
    return res.json()["user_id"]


@pytest.fixture
def uploads_dir(tmp_path):
    return tmp_path / "uploads"
