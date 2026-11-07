"""Speech recognition with hosted Whisper large-v3 (Groq or OpenAI; same API shape).

`transcribe()` gets one guess. `build_prompt()` makes the hint text from the user's personal
words and most-used approved phrases, so Whisper expects *their* vocabulary.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.config import get_settings
from app.db import aggregate
from app.text import normalize

logger = logging.getLogger("echo.asr")

PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1/audio/transcriptions", "whisper-large-v3"),
    "openai": ("https://api.openai.com/v1/audio/transcriptions", "whisper-1"),
}
# Second Groq model for the extra guess: same quality family, separate rate limit.
ALT_MODEL = "whisper-large-v3-turbo"
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


_shared: httpx.AsyncClient | None = None


def shared_client() -> httpx.AsyncClient:
    """One long-lived HTTP client: later requests reuse the open connection (no new TLS handshake)."""
    global _shared
    if _shared is None or _shared.is_closed:
        _shared = httpx.AsyncClient(timeout=30, limits=httpx.Limits(max_keepalive_connections=10))
    return _shared


async def close_shared_client() -> None:
    global _shared
    if _shared is not None:
        await _shared.aclose()
    _shared = None


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
    model: str | None = None,
) -> Transcript:
    """One Whisper guess for a WAV file.

    language: "tr"/"en" to force a language, or None to auto-detect (mixed-language users).
    prompt:   hint text with words the user is likely to say.
    model:    override the Whisper model (e.g. the turbo variant).
    """
    url, default_model, key = _provider()
    model = model or default_model
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


# How many names / phrases go into the Whisper hint. Short lists work better: a long list of
# names can pull Whisper toward the wrong one (measured: "Eylül" heard as "Zeynep").
MAX_HINT_WORDS = 12
NAME_TOKEN = re.compile(r"\b([A-ZÇĞİÖŞÜ][\wçğıöşüâîû]+)(?:['’][\wçğıöşü]+)?", re.UNICODE)


async def _approved_counts(db, user_id: str) -> dict[str, float]:
    """Approved sentence -> how often it was said (helper corrections count double: they are the truth)."""
    pipeline = [
        {"$match": {"user_id": user_id, "status": "approved"}},
        {"$group": {
            "_id": {"$ifNull": ["$final_text", "$sentence"]},
            "n": {"$sum": 1},
            "corrected": {"$sum": {"$cond": [{"$eq": ["$was_corrected", True]}, 1, 0]}},
        }},
        {"$sort": {"n": -1}},
        {"$limit": 200},
    ]
    return {d["_id"]: d["n"] + d["corrected"] for d in await aggregate(db.utterances, pipeline) if d["_id"]}


def learned_names(sentences: dict[str, float], known: set[str], min_weight: float = 2) -> list[str]:
    """Names the user says often that aren't in their personal words (capitalised words not at
    the start of a sentence, Turkish suffixes like 'Özgür'ü' removed)."""
    weights: dict[str, float] = {}
    for text, n in sentences.items():
        for i, m in enumerate(NAME_TOKEN.finditer(text)):
            if m.start() == 0 or text[: m.start()].rstrip().endswith((".", "!", "?")):
                continue  # a capital at the start of a sentence is not a name
            name = m.group(1)
            if name.casefold() not in known:
                weights[name] = weights.get(name, 0) + n
    return [w for w, n in sorted(weights.items(), key=lambda kv: -kv[1]) if n >= min_weight]


async def build_prompt(db, user_id: str, top_phrases: int = 10) -> str:
    """Hint text for Whisper, rebuilt on every request (so every approval counts immediately):
    the user's most-used names first, names learned from approved sentences, then their most
    frequent approved sentences."""
    words = [d["word"] async for d in db.personal_words.find({"user_id": user_id}, {"word": 1}).sort("created_at", 1)]
    sentences = await _approved_counts(db, user_id)
    lowered = {t: t.casefold() for t in sentences}

    def usage(word: str) -> float:
        w = word.casefold()
        return sum(n for t, n in sentences.items() if w in lowered[t])

    ranked = sorted(words, key=lambda w: -usage(w))  # stable: unused words keep the order they were added
    names = (ranked + learned_names(sentences, {w.casefold() for w in words}))[:MAX_HINT_WORDS]
    phrases = list(sentences)[:top_phrases]

    parts = []
    if names:
        parts.append(", ".join(names) + ".")
    parts.extend(p if p.endswith((".", "?", "!")) else p + "." for p in phrases)
    return " ".join(parts)[:MAX_PROMPT_CHARS]


def _is_hallucination(t: Transcript, prompt: str | None) -> bool:
    """Whisper sometimes repeats the prompt, or invents text, when it hears no clear speech."""
    text = normalize(t.text)
    if not text:
        return True
    if prompt and t.prompt_used and len(text) > 8 and text in normalize(prompt):
        return True
    return (t.no_speech_prob or 0) > 0.8 and (t.avg_logprob or 0) < -1.0


async def get_candidates(wav: Path, language: str | None, prompt: str | None) -> list[Transcript]:
    """2-3 different Whisper guesses for the same recording, best first, duplicates removed.

    Runs in parallel: with the personal prompt, without it, and with the prompt at
    temperature 0.4 (a slightly more adventurous guess). On Groq the third guess uses the
    turbo model, which has its own rate limit (free tier: 20 requests/minute per model).
    """
    alt = ALT_MODEL if _provider()[1] == PROVIDERS["groq"][1] else None
    variants: list[tuple[str | None, float, str | None]] = (
        [(prompt, 0.0, None), (None, 0.0, None), (prompt, 0.4, alt)] if prompt else [(None, 0.0, None), (None, 0.4, alt)]
    )
    client = shared_client()
    results = await asyncio.gather(
        *(transcribe(wav, language, p, temp, client=client, model=m) for p, temp, m in variants),
        return_exceptions=True,
    )
    errors = [r for r in results if isinstance(r, Exception)]
    for err in errors:
        logger.warning("One Whisper guess failed: %s", err)

    candidates: list[Transcript] = []
    seen: set[str] = set()
    for r in results:
        if isinstance(r, Exception) or _is_hallucination(r, prompt):
            continue
        key = normalize(r.text)
        if key not in seen:
            seen.add(key)
            candidates.append(r)
    if not candidates and len(errors) == len(results):
        raise ASRError(f"All Whisper guesses failed: {errors[0]}")
    return candidates
