"""The ElevenLabs "out of credits" pause (no real calls)."""

import asyncio

import httpx

from app.services import elevenlabs, tts

QUOTA = '{"detail":{"type":"invalid_request","code":"quota_exceeded","message":"You have 0 credits remaining"}}'


def fake_client(seen, status, body="error"):
    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(status, text=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def speak(client):
    try:
        asyncio.run(tts.synthesize("Merhaba", "tr", client=client))
    except tts.TTSUnavailable as exc:
        return str(exc)
    return "spoke"


def test_out_of_credits_pauses_elevenlabs():
    seen = []
    assert "quota_exceeded" in speak(fake_client(seen, 401, QUOTA))
    assert elevenlabs.out_of_credits() and elevenlabs.status() == "out of credits"
    # The next sentence doesn't call ElevenLabs at all: the app uses the browser voice straight away.
    assert "out of credits" in speak(fake_client(seen, 200))
    assert len(seen) == 1


def test_other_errors_do_not_pause_elevenlabs():
    assert "500" in speak(fake_client([], 500, "boom"))
    assert not elevenlabs.out_of_credits()


def test_health_reports_elevenlabs(client):
    assert client.get("/health").json()["features"]["elevenlabs"] == "on"
