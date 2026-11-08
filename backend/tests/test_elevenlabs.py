"""ElevenLabs: Scribe as an extra speech-to-text reading, and the "out of credits" pause (no real calls)."""

import asyncio

import httpx

from app.services import asr, elevenlabs, tts
from app.services.asr import Transcript

QUOTA = '{"detail":{"type":"invalid_request","code":"quota_exceeded","message":"You have 0 credits remaining"}}'


def scribe_client(seen, status=200, body=None):
    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if status != 200:
            return httpx.Response(status, text=body or "error")
        return httpx.Response(200, json=body or {
            "language_code": "tur", "language_probability": 0.97, "text": " Boncuk'a mama verdin mi? ",
            "words": [{"text": "Boncuk'a", "type": "word", "logprob": -0.1}, {"text": " ", "type": "spacing", "logprob": 0},
                      {"text": "mama", "type": "word", "logprob": -0.3}],
        })

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_scribe_reading_is_parsed_with_keyterms_and_language(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF....WAVE")
    seen = []
    t = asyncio.run(asr.scribe(wav, "tr", "Zeynep, Boncuk. Mama verdin mi?", scribe_client(seen)))
    assert (t.text, t.language, t.engine, t.reading) == ("Boncuk'a mama verdin mi?", "tr", "elevenlabs", "elevenlabs:tr")
    assert abs(t.avg_logprob - (-0.2)) < 1e-9  # spacing tokens left out
    req = seen[0]
    assert req.url.path == "/v1/speech-to-text" and req.headers["xi-api-key"] == "test-elevenlabs"
    body = req.content.decode("utf-8", "ignore")
    assert "scribe_v2" in body and 'name="language_code"' in body
    for term in ("Zeynep", "Boncuk", "Mama verdin mi"):
        assert term in body


def test_keyterms_follow_scribes_limits():
    assert asr.hint_keyterms("Zeynep, Kadıköy. Su istiyorum.") == ["Zeynep", "Kadıköy", "Su istiyorum"]
    long = "Bu cümle beş kelimeden çok daha uzun bir cümle."
    assert elevenlabs.keyterms(["Ali", "ali", long, "a{b}", "x" * 60]) == ["Ali"]
    assert asr.hint_keyterms(None) == []


def test_scribe_adds_a_reading_next_to_whisper(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_STT", "true")
    from app.config import get_settings

    get_settings.cache_clear()

    async def whisper(wav, language=None, prompt=None, temperature=0.0, client=None, model=None):
        return Transcript(text="Su istiyorum", language="tr", prompt_used=bool(prompt), temperature=temperature, forced_language=language)

    async def scribe(wav, language, prompt, client):
        return Transcript(text="Su istiyorum.", language="tr", forced_language=language, engine="elevenlabs")

    monkeypatch.setattr(asr, "transcribe", whisper)
    monkeypatch.setattr(asr, "scribe", scribe)
    [cand] = asyncio.run(asr.get_candidates("x.wav", None, "Zeynep.", languages=["tr", "en"]))
    assert "auto:None" not in cand.readings and cand.readings.count("elevenlabs:auto:tr") == 1

    from app.services.translate import describe_readings

    assert "auto-detected Turkish by ElevenLabs" in describe_readings(cand)


def test_out_of_credits_pauses_elevenlabs(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_STT", "true")
    from app.config import get_settings

    get_settings.cache_clear()
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF....WAVE")
    seen = []
    try:
        asyncio.run(elevenlabs.transcribe(wav, "tr", [], scribe_client(seen, 401, QUOTA)))
    except elevenlabs.STTError:
        pass
    assert elevenlabs.out_of_credits() and not elevenlabs.stt_enabled() and elevenlabs.status() == "out of credits"
    # TTS stops calling ElevenLabs too (no request leaves the server)
    try:
        asyncio.run(tts.synthesize("Merhaba", "tr", client=scribe_client(seen)))
        raised = False
    except tts.TTSUnavailable as exc:
        raised = "out of credits" in str(exc)
    assert raised and len(seen) == 1


def test_other_errors_do_not_pause_elevenlabs(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF....WAVE")
    try:
        asyncio.run(elevenlabs.transcribe(wav, None, [], scribe_client([], 500, "boom")))
    except elevenlabs.STTError:
        pass
    assert not elevenlabs.out_of_credits()


def test_health_reports_elevenlabs(client):
    features = client.get("/health").json()["features"]
    assert features["tts"] == "elevenlabs" and features["elevenlabs"] == "on"
