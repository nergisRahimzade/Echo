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
    body = req.content.replace(b" ", b"")
    assert b'"model_id":"eleven_multilingual_v2"' in body and b'"language_code":"tr"' in body
    assert b'"speed":0.9' in body  # a little slower than normal
    assert req.url.path.endswith("/cgSgspJ2msm6clMCkdW9")  # default voice: Jessica (American, warm)


def test_turkish_and_english_cached_separately(client, eleven):
    client.post("/tts", json={"text": "Hello", "language": "en"})
    client.post("/tts", json={"text": "Hello", "language": "tr"})
    assert len(eleven) == 2


def test_chosen_voice_is_used_and_cached_separately(client, eleven):
    client.post("/tts", json={"text": "Hello", "language": "en", "voice": "will"})
    client.post("/tts", json={"text": "Hello", "language": "en", "voice": "sarah"})
    client.post("/tts", json={"text": "Hello", "language": "en", "voice": "will"})
    assert len(eleven) == 2  # the third one is a cache hit
    assert eleven[0].url.path.endswith("/bIHbv24MWmeRgasZH58o") and eleven[1].url.path.endswith("/EXAVITQu4vr4xnSDxMaL")


def test_unknown_or_unset_voice_rejected(client, eleven):
    assert client.post("/tts", json={"text": "Hi", "language": "en", "voice": "robot"}).status_code == 422
    assert client.post("/tts", json={"text": "Hi", "language": "en", "voice": "girl"}).status_code == 422  # not set up


def test_voices_lists_american_adults_and_missing_children(client):
    body = client.get("/voices").json()
    assert body["enabled"] is True and body["default"] == "jessica"
    kinds = [v["kind"] for v in body["voices"]]
    assert kinds.count("woman") >= 1 and kinds.count("man") >= 1
    assert body["missing"] == ["girl", "boy"]


def test_child_voices_offered_once_configured(client, eleven, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("ELEVENLABS_VOICE_GIRL", "girl-voice-id")
    monkeypatch.setenv("ELEVENLABS_VOICE_BOY", "boy-voice-id")
    get_settings.cache_clear()
    body = client.get("/voices").json()
    assert {"girl", "boy"} <= {v["kind"] for v in body["voices"]} and body["missing"] == []
    assert client.post("/tts", json={"text": "Hi", "language": "en", "voice": "boy"}).status_code == 200
    assert eleven[-1].url.path.endswith("/boy-voice-id")


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
