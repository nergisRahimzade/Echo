"""Shared test setup: fake keys so the app can be imported without a real backend/.env."""

import pytest

FAKE_ENV = {
    "ANTHROPIC_API_KEY": "test-anthropic",
    "GROQ_API_KEY": "test-groq",
    "OPENAI_API_KEY": "",
    "ELEVENLABS_API_KEY": "test-elevenlabs",
    # Nothing listens here, so tests never touch a real database.
    "MONGODB_URI": "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=200",
    "MONGODB_DB": "echo_test",
    "EMBEDDING_API_KEY": "test-embedding",
    "FRONTEND_URL": "http://localhost:3000",
}


@pytest.fixture(autouse=True)
def fake_env(monkeypatch):
    for key, value in FAKE_ENV.items():
        monkeypatch.setenv(key, value)
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
