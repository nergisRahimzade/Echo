import asyncio
import json

import httpx
import pytest

from app.services import asr


def fake_whisper(responses, seen):
    """httpx transport that records requests and replies with queued responses."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        status, body = responses.pop(0)
        return httpx.Response(status, json=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


VERBOSE = {
    "text": " Su istiyorum. ",
    "language": "turkish",
    "segments": [{"avg_logprob": -0.2, "no_speech_prob": 0.01}, {"avg_logprob": -0.4, "no_speech_prob": 0.05}],
}


@pytest.fixture
def wav(tmp_path):
    p = tmp_path / "a.wav"
    p.write_bytes(b"RIFF....WAVE")
    return p


def test_transcribe_parses_text_language_and_confidence(wav):
    seen = []
    client = fake_whisper([(200, VERBOSE)], seen)
    t = asyncio.run(asr.transcribe(wav, language="tr", prompt="Zeynep, Kadıköy.", client=client))
    assert t.text == "Su istiyorum."
    assert t.language == "tr"
    assert t.avg_logprob == pytest.approx(-0.3)
    assert t.no_speech_prob == pytest.approx(0.05)
    assert t.prompt_used is True
    req = seen[0]
    assert str(req.url) == "https://api.groq.com/openai/v1/audio/transcriptions"
    assert req.headers["authorization"] == "Bearer test-groq"
    body = req.content.decode("utf-8", "ignore")
    for field in ('name="model"', "whisper-large-v3", 'name="language"', 'name="prompt"', "Kadıköy", "verbose_json"):
        assert field in body


def test_auto_detect_sends_no_language(wav):
    seen = []
    asyncio.run(asr.transcribe(wav, language=None, client=fake_whisper([(200, VERBOSE)], seen)))
    assert 'name="language"' not in seen[0].content.decode("utf-8", "ignore")


def test_retries_on_rate_limit(wav):
    seen = []
    client = fake_whisper([(429, {"error": "slow down"}), (200, VERBOSE)], seen)
    assert asyncio.run(asr.transcribe(wav, client=client)).text == "Su istiyorum."
    assert len(seen) == 2


def test_bad_request_raises(wav):
    with pytest.raises(asr.ASRError, match="400"):
        asyncio.run(asr.transcribe(wav, client=fake_whisper([(400, {"error": "bad file"})], [])))


def test_openai_used_when_no_groq_key(wav, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    get_settings.cache_clear()
    seen = []
    asyncio.run(asr.transcribe(wav, client=fake_whisper([(200, VERBOSE)], seen)))
    assert seen[0].url.host == "api.openai.com"
    assert "whisper-1" in seen[0].content.decode("utf-8", "ignore")


def test_build_prompt_uses_words_and_top_phrases(fake_db):
    async def run():
        await fake_db.personal_words.insert_many([{"user_id": "u", "word": "Zeynep"}, {"user_id": "u", "word": "Kadıköy"}])
        docs = [{"user_id": "u", "status": "approved", "final_text": "Su istiyorum"} for _ in range(3)]
        docs += [{"user_id": "u", "status": "approved", "sentence": "Merhaba"}]
        docs += [{"user_id": "u", "status": "rejected", "sentence": "Yanlış"}]
        docs += [{"user_id": "other", "status": "approved", "sentence": "Başkası"}]
        await fake_db.utterances.insert_many(docs)
        return await asr.build_prompt(fake_db, "u")

    prompt = asyncio.run(run())
    assert prompt == "Zeynep, Kadıköy. Su istiyorum. Merhaba."


def test_build_prompt_empty_for_new_user(fake_db):
    assert asyncio.run(asr.build_prompt(fake_db, "nobody")) == ""
