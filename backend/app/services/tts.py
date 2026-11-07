"""Text-to-speech with ElevenLabs multilingual voices, cached by voice + text so repeats are instant and free.

Without ELEVENLABS_API_KEY this service is disabled and the app uses the browser's own voice.
"""

import hashlib
import logging
from pathlib import Path

import httpx
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.services import voices

logger = logging.getLogger("echo.tts")
API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


class TTSUnavailable(RuntimeError):
    """No key configured, or ElevenLabs could not produce audio."""


def enabled() -> bool:
    return bool(get_settings().elevenlabs_api_key)


# Lower stability + some style = livelier, more expressive delivery (ElevenLabs' defaults sound flat).
VOICE_SETTINGS = {"stability": 0.4, "similarity_boost": 0.75, "style": 0.3, "use_speaker_boost": True}


def cache_path(text: str, language: str, elevenlabs_id: str) -> Path:
    s = get_settings()
    key = f"{s.elevenlabs_model}|{elevenlabs_id}|{VOICE_SETTINGS}|{language}|{text}".encode("utf-8")
    return s.uploads_dir / "tts-cache" / f"{hashlib.sha256(key).hexdigest()}.mp3"


async def forget(texts: set[str]) -> int:
    """Delete cached audio of these sentences in every voice and language (privacy: delete my data)."""
    paths = {
        cache_path(text, language, v.elevenlabs_id)
        for text in texts
        for language in ("tr", "en")
        for v in voices.available()
    }

    def remove() -> int:
        removed = 0
        for p in paths:
            if p.exists():
                p.unlink(missing_ok=True)
                removed += 1
        return removed

    return await run_in_threadpool(remove)


async def synthesize(
    text: str, language: str, voice: str | None = None, client: httpx.AsyncClient | None = None
) -> tuple[bytes, bool]:
    """MP3 bytes for `text` in the chosen voice (see services/voices.py) and whether it came from the cache."""
    s = get_settings()
    if not s.elevenlabs_api_key:
        raise TTSUnavailable("ELEVENLABS_API_KEY is not set")
    elevenlabs_id = voices.get(voice).elevenlabs_id
    path = cache_path(text, language, elevenlabs_id)
    if path.exists():
        return await run_in_threadpool(path.read_bytes), True

    own = client is None
    client = client or httpx.AsyncClient(timeout=20)
    try:
        res = await client.post(
            API.format(voice_id=elevenlabs_id),
            params={"output_format": "mp3_44100_128"},
            headers={"xi-api-key": s.elevenlabs_api_key, "accept": "audio/mpeg"},
            json={
                "text": text,
                "model_id": s.elevenlabs_model,
                "language_code": language,
                "voice_settings": VOICE_SETTINGS,
            },
        )
    except httpx.HTTPError as exc:
        raise TTSUnavailable(f"ElevenLabs request failed: {exc}") from exc
    finally:
        if own:
            await client.aclose()
    if res.status_code != 200 or not res.content:
        raise TTSUnavailable(f"ElevenLabs error {res.status_code}: {res.text[:200]}")

    def save() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(res.content)

    await run_in_threadpool(save)
    return res.content, False
