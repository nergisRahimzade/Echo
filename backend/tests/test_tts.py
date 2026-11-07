import asyncio

import httpx
import pytest

from app.services import tts


@pytest.fixture
def eleven(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-eleven")
    get_settings.cache_clear()
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=b"ID3fake-mp3")

    real = httpx.AsyncClient
    monkeypatch.setattr(tts.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler)))
    return calls


def test_tts_returns_mp3_and_caches(client, eleven):
    r1 = client.post("/tts", json={"text": "Su istiyorum.", "language": "tr"})
    assert r1.status_code == 200 and r1.headers["content-type"] == "audio/mpeg"
    assert r1.content == b"ID3fake-mp3" and r1.headers["x-tts-cache"] == "miss"
    r2 = client.post("/tts", json={"text": "Su istiyorum.", "language": "tr"})
    assert r2.headers["x-tts-cache"] == "hit" and len(eleven) == 1  # second time served from cache
    req = eleven[0]
    assert req.headers["xi-api-key"] == "test-eleven"
    assert b'"model_id":"eleven_flash_v2_5"' in req.content.replace(b" ", b"") and b'"language_code":"tr"' in req.content.replace(b" ", b"")


def test_turkish_and_english_cached_separately(client, eleven):
    client.post("/tts", json={"text": "Hello", "language": "en"})
    client.post("/tts", json={"text": "Hello", "language": "tr"})
    assert len(eleven) == 2


def test_no_key_means_503_use_browser_voice(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("ELEVENLABS_API_KEY", "")
    get_settings.cache_clear()
    r = client.post("/tts", json={"text": "Merhaba", "language": "tr"})
    assert r.status_code == 503


def test_validation(client):
    assert client.post("/tts", json={"text": " ", "language": "tr"}).status_code == 422
    assert client.post("/tts", json={"text": "hi", "language": "fr"}).status_code == 422


def test_elevenlabs_error_becomes_unavailable(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    get_settings.cache_clear()
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(401, text="bad key")))
    with pytest.raises(tts.TTSUnavailable, match="401"):
        asyncio.run(tts.synthesize("x", "en", client=client))


def test_health_reports_features(client):
    body = client.get("/health").json()
    assert body["features"] == {"tts": "elevenlabs", "embeddings": "voyage"}
