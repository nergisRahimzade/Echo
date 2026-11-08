"""ElevenLabs, shared by text-to-speech (services/tts.py) and speech-to-text (Scribe, here).

When the account runs out of credits ElevenLabs answers every request with "quota_exceeded".
That is remembered for a while, so requests skip ElevenLabs straight away (the browser voice and
the Whisper guesses carry on) instead of waiting for an answer that is sure to be "no".
"""

import logging
import time
from pathlib import Path

import httpx

from app.config import get_settings

logger = logging.getLogger("echo.elevenlabs")

API = "https://api.elevenlabs.io/v1"
# How long to skip ElevenLabs after it says the account has no credits left.
EMPTY_PAUSE_SECONDS = 15 * 60
# Scribe answers with ISO 639-3 codes ("tur"); the rest of Echo uses 639-1 ("tr").
LANGUAGE_CODES = {"tur": "tr", "eng": "en"}
# Scribe keyterm limits (docs): at most 50 characters and 5 words each.
MAX_KEYTERMS, MAX_KEYTERM_CHARS, MAX_KEYTERM_WORDS = 50, 50, 5
FORBIDDEN_IN_KEYTERMS = set("<>{}[]\\")

_empty_until = 0.0


def enabled() -> bool:
    return bool(get_settings().elevenlabs_api_key)


def out_of_credits() -> bool:
    return time.monotonic() < _empty_until


def note_response(res: httpx.Response) -> None:
    """Call with every failed ElevenLabs response: notices an empty account."""
    global _empty_until
    if res.status_code in (401, 402, 429) and "quota_exceeded" in res.text:
        if not out_of_credits():
            logger.warning("ElevenLabs has no credits left: skipping it for %d minutes.", EMPTY_PAUSE_SECONDS // 60)
        _empty_until = time.monotonic() + EMPTY_PAUSE_SECONDS


def reset() -> None:
    """Forget the "out of credits" state (tests)."""
    global _empty_until
    _empty_until = 0.0


def status() -> str:
    """For /health: "off" (no key), "out of credits", or "on"."""
    if not enabled():
        return "off"
    return "out of credits" if out_of_credits() else "on"


def stt_enabled() -> bool:
    s = get_settings()
    return bool(s.elevenlabs_api_key and s.elevenlabs_stt) and not out_of_credits()


def keyterms(words: list[str]) -> list[str]:
    """The words worth biasing Scribe towards, cut to Scribe's limits, duplicates removed."""
    out: list[str] = []
    seen: set[str] = set()
    for w in words:
        w = " ".join(w.split()).strip(" .,!?")
        if (
            not w or len(w) > MAX_KEYTERM_CHARS or len(w.split()) > MAX_KEYTERM_WORDS
            or FORBIDDEN_IN_KEYTERMS & set(w) or w.casefold() in seen
        ):
            continue
        seen.add(w.casefold())
        out.append(w)
    return out[:MAX_KEYTERMS]


class STTError(RuntimeError):
    """Scribe could not be reached, rejected the audio, or the account is out of credits."""


async def transcribe(wav: Path, language: str | None, terms: list[str], client: httpx.AsyncClient) -> dict:
    """One Scribe reading of a WAV file. Returns {"text", "language", "avg_logprob"}.

    language: "tr"/"en" to tell Scribe the language, None to let it detect it.
    terms:    names and short phrases this person says (keyterm biasing).
    """
    s = get_settings()
    if not s.elevenlabs_api_key:
        raise STTError("ELEVENLABS_API_KEY is not set")
    if out_of_credits():
        raise STTError("ElevenLabs is out of credits")
    audio = Path(wav).read_bytes()
    data: dict = {"model_id": s.elevenlabs_stt_model, "tag_audio_events": "false", "timestamps_granularity": "word"}
    if language:
        data["language_code"] = language

    async def post(with_terms: bool) -> httpx.Response:
        fields = {**data, "keyterms": terms} if with_terms and terms else data
        return await client.post(
            f"{API}/speech-to-text",
            headers={"xi-api-key": s.elevenlabs_api_key},
            data=fields,
            files={"file": ("audio.wav", audio, "audio/wav")},
            timeout=30,
        )

    try:
        res = await post(with_terms=True)
        if res.status_code == 422 and terms:
            logger.warning("Scribe rejected the keyterms, retrying without them: %s", res.text[:200])
            res = await post(with_terms=False)
    except httpx.HTTPError as exc:
        raise STTError(f"ElevenLabs request failed: {exc}") from exc
    if res.status_code != 200:
        note_response(res)
        raise STTError(f"ElevenLabs error {res.status_code}: {res.text[:200]}")

    body = res.json()
    words = [w for w in body.get("words") or [] if w.get("type") == "word"]
    logprobs = [w["logprob"] for w in words if isinstance(w.get("logprob"), (int, float))]
    code = (body.get("language_code") or "").lower()
    return {
        "text": (body.get("text") or "").strip(),
        "language": LANGUAGE_CODES.get(code, code if len(code) == 2 else None),
        "avg_logprob": sum(logprobs) / len(logprobs) if logprobs else None,
    }
