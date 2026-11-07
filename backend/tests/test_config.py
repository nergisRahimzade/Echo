import pytest

from app.config import MissingSettingsError, load_settings


def test_loads_when_all_keys_present():
    s = load_settings(env_file=None)
    assert s.anthropic_api_key == "test-anthropic"
    assert s.groq_api_key == "test-groq"
    assert s.openai_api_key is None  # blank counts as not set
    assert s.mongodb_db == "echo_test"
    assert s.frontend_origins == ["http://localhost:3000"]


def test_missing_key_gives_clear_message(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "   ")  # blank also counts as missing
    with pytest.raises(MissingSettingsError) as info:
        load_settings(env_file=None)
    message = str(info.value)
    assert "ANTHROPIC_API_KEY" in message
    assert "ELEVENLABS_API_KEY" in message
    assert ".env.example" in message


def test_all_problems_listed_together(monkeypatch):
    monkeypatch.delenv("MONGODB_URI")
    monkeypatch.setenv("GROQ_API_KEY", "")
    with pytest.raises(MissingSettingsError) as info:
        load_settings(env_file=None)
    assert "MONGODB_URI" in str(info.value)
    assert "OPENAI_API_KEY or GROQ_API_KEY" in str(info.value)


def test_needs_one_whisper_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    with pytest.raises(MissingSettingsError, match="OPENAI_API_KEY or GROQ_API_KEY"):
        load_settings(env_file=None)


def test_openai_alone_is_enough(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    assert load_settings(env_file=None).openai_api_key == "test-openai"


def test_multiple_frontend_origins(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000, https://echo.vercel.app")
    assert load_settings(env_file=None).frontend_origins == [
        "http://localhost:3000",
        "https://echo.vercel.app",
    ]
