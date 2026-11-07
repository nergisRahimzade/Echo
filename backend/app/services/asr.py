"""Speech recognition with hosted Whisper large-v3 (Groq or OpenAI; same API shape).

`transcribe()` gets one guess. `build_prompt()` makes the hint text from the user's personal
words and most-used approved phrases, so Whisper expects *their* vocabulary.
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.config import get_settings
from app.db import aggregate

logger = logging.getLogger("echo.asr")

PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1/audio/transcriptions", "whisper-large-v3"),
    "openai": ("https://api.openai.com/v1/audio/transcriptions", "whisper-1"),
}
# Whisper's verbose_json reports the language as an English name; we use ISO codes.
LANGUAGE_CODES = {"turkish": "tr", "english": "en", "arabic": "ar", "spanish": "es", "german": "de"}
# Whisper only reads the last ~224 tokens of a prompt; keep it comfortably short.
MAX_PROMPT_CHARS = 600


class ASRError(RuntimeError):
    """Whisper could not be reached or rejected the audio."""


@dataclass
class Transcript:
    text: str
    language: str | None  # ISO code, e.g. "tr"
    avg_logprob: float | None = None  # Whisper's own certainty (closer to 0 = surer)
    no_speech_prob: float | None = None
    prompt_used: bool = False
    temperature: float = 0.0


def _provider() -> tuple[str, str, str]:
    """(url, model, api key) for the configured provider. Groq preferred: faster."""
    s = get_settings()
    if s.groq_api_key:
        url, model = PROVIDERS["groq"]
        return url, s.whisper_model or model, s.groq_api_key
    if s.openai_api_key:
        url, model = PROVIDERS["openai"]
        return url, s.whisper_model or model, s.openai_api_key
    raise ASRError("No Whisper key configured (GROQ_API_KEY or OPENAI_API_KEY).")


def _language_code(name: str | None) -> str | None:
    if not name:
        return None
    name = name.strip().lower()
    return name if len(name) == 2 else LANGUAGE_CODES.get(name, name)


def _parse(body: dict, prompt_used: bool, temperature: float) -> Transcript:
    segments = body.get("segments") or []
    logprobs = [s["avg_logprob"] for s in segments if s.get("avg_logprob") is not None]
    no_speech = [s["no_speech_prob"] for s in segments if s.get("no_speech_prob") is not None]
    return Transcript(
        text=(body.get("text") or "").strip(),
        language=_language_code(body.get("language")),
        avg_logprob=sum(logprobs) / len(logprobs) if logprobs else None,
        no_speech_prob=max(no_speech) if no_speech else None,
        prompt_used=prompt_used,
        temperature=temperature,
    )


async def transcribe(
    wav: Path,
    language: str | None = None,
    prompt: str | None = None,
    temperature: float = 0.0,
    client: httpx.AsyncClient | None = None,
) -> Transcript:
    """One Whisper guess for a WAV file.

    language: "tr"/"en" to force a language, or None to auto-detect (mixed-language users).
    prompt:   hint text with words the user is likely to say.
    """
    url, model, key = _provider()
    data = {"model": model, "response_format": "verbose_json", "temperature": str(temperature)}
    if language:
        data["language"] = language
    if prompt:
        data["prompt"] = prompt[:MAX_PROMPT_CHARS]
    audio = Path(wav).read_bytes()

    own_client = client is None
    client = client or httpx.AsyncClient(timeout=30)
    try:
        for attempt in range(3):
            try:
                res = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {key}"},
                    data=data,
                    files={"file": (Path(wav).name, audio, "audio/wav")},
                )
            except httpx.HTTPError as exc:
                if attempt == 2:
                    raise ASRError(f"Whisper request failed: {exc}") from exc
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            if res.status_code == 429 or res.status_code >= 500:  # rate limit / provider hiccup
                if attempt < 2:
                    wait = float(res.headers.get("retry-after", 0.5 * (attempt + 1)))
                    await asyncio.sleep(min(wait, 3))
                    continue
            if res.status_code != 200:
                raise ASRError(f"Whisper error {res.status_code}: {res.text[:300]}")
            return _parse(res.json(), prompt_used=bool(prompt), temperature=temperature)
        raise ASRError("Whisper kept failing after retries.")
    finally:
        if own_client:
            await client.aclose()


async def build_prompt(db, user_id: str, top_phrases: int = 10) -> str:
    """Hint text: the user's personal words + their most-used approved sentences."""
    words = [d["word"] async for d in db.personal_words.find({"user_id": user_id}, {"word": 1})]
    pipeline = [
        {"$match": {"user_id": user_id, "status": "approved"}},
        {"$group": {"_id": {"$ifNull": ["$final_text", "$sentence"]}, "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
        {"$limit": top_phrases},
    ]
    phrases = [d["_id"] for d in await aggregate(db.utterances, pipeline) if d["_id"]]
    parts = []
    if words:
        parts.append(", ".join(words) + ".")
    parts.extend(p if p.endswith((".", "?", "!")) else p + "." for p in phrases)
    return " ".join(parts)[:MAX_PROMPT_CHARS]
