"""Speech recognition with hosted Whisper large-v3 (Groq or OpenAI; same API shape), plus one
ElevenLabs Scribe reading when an ElevenLabs key is set (services/elevenlabs.py).

`transcribe()` gets one guess. `build_prompt()` makes the hint text from the user's personal
words and most-used approved phrases, so Whisper expects *their* vocabulary.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.config import get_settings
from app.db import aggregate
from app.services import elevenlabs
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
    forced_language: str | None = None  # the language Whisper was told to use (None = auto-detect)
    # Every reading that produced this same text, e.g. ["tr", "en", "auto:en"] (filled when merging).
    readings: list[str] = field(default_factory=list)
    engine: str = "whisper"  # or "elevenlabs" (Scribe)

    @property
    def reading(self) -> str:
        base = self.forced_language or f"auto:{self.language}"
        return base if self.engine == "whisper" else f"{self.engine}:{base}"

    @property
    def certainty(self) -> str:
        """Whisper's own certainty in plain words, for the agent."""
        lp = self.avg_logprob
        if lp is None:
            return "unknown"
        return "high" if lp > -0.35 else "medium" if lp > -0.7 else "low"


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


def _parse(body: dict, prompt_used: bool, temperature: float, forced_language: str | None = None) -> Transcript:
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
        forced_language=forced_language,
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
            return _parse(res.json(), prompt_used=bool(prompt), temperature=temperature, forced_language=language)
        raise ASRError("Whisper kept failing after retries.")
    finally:
        if own_client:
            await client.aclose()


# How many names / phrases go into the Whisper hint. Short lists work better: a long list of
# names can pull Whisper toward the wrong one (measured: "Eylül" heard as "Zeynep").
MAX_HINT_WORDS = 12
NAME_TOKEN = re.compile(r"\b([A-ZÇĞİÖŞÜ][\wçğıöşüâîû]+)(?:['’][\wçğıöşü]+)?", re.UNICODE)


# A sentence only approved by silence (spoken, nobody pressed thumbs-down) counts half: on its
# own it doesn't reach the hint, so a mistake nobody noticed isn't fed back to Whisper. Said
# twice that way, or confirmed once by a person, it does.
SILENT_APPROVAL_WEIGHT = 0.5
MIN_HINT_WEIGHT = 1.0


async def _approved_counts(db, user_id: str) -> dict[str, float]:
    """Approved sentence -> how much it counts, highest first: 1 per thumbs-up, 0.5 per silent
    approval, +1 per helper correction (they are the truth). Disputed examples are left out."""
    pipeline = [
        {"$match": {"user_id": user_id, "status": "approved", "disputed": {"$ne": True}}},
        {"$group": {
            "_id": {"$ifNull": ["$final_text", "$sentence"]},
            "n": {"$sum": {"$cond": [{"$eq": ["$auto_approved", True]}, SILENT_APPROVAL_WEIGHT, 1]}},
            "corrected": {"$sum": {"$cond": [{"$eq": ["$was_corrected", True]}, 1, 0]}},
        }},
        {"$sort": {"n": -1}},
        {"$limit": 200},
    ]
    counts = {d["_id"]: d["n"] + d["corrected"] for d in await aggregate(db.utterances, pipeline) if d["_id"]}
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))  # stable: ties keep the database order


async def _enrolled_phrases(db, user_id: str, language: str | None) -> list[str]:
    """The phrases this user recorded during enrollment, most re-recorded first. A one-language
    user only gets phrases in that language: Whisper is forced into it."""
    query: dict = {"user_id": user_id}
    if language in ("tr", "en"):
        query["language"] = language
    counts: dict[str, int] = {}
    async for d in db.enrollment_samples.find(query, {"text": 1}).sort("created_at", 1):
        if d.get("text"):
            counts[d["text"]] = counts.get(d["text"], 0) + 1
    return sorted(counts, key=lambda t: -counts[t])


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


async def build_prompt(db, user_id: str, top_phrases: int = 10, language: str | None = None) -> str:
    """Hint text for Whisper, rebuilt on every request (so every approval counts immediately):
    the user's most-used names first, names learned from approved sentences, then their most
    frequent approved sentences, topped up with their enrollment phrases while there are fewer
    than `top_phrases` of those (so a new user's hint isn't empty)."""
    words = [d["word"] async for d in db.personal_words.find({"user_id": user_id}, {"word": 1}).sort("created_at", 1)]
    sentences = await _approved_counts(db, user_id)
    lowered = {t: t.casefold() for t in sentences}

    def usage(word: str) -> float:
        w = word.casefold()
        return sum(n for t, n in sentences.items() if w in lowered[t])

    ranked = sorted(words, key=lambda w: -usage(w))  # stable: unused words keep the order they were added
    names = (ranked + learned_names(sentences, {w.casefold() for w in words}))[:MAX_HINT_WORDS]
    phrases = [t for t, n in sentences.items() if n >= MIN_HINT_WEIGHT][:top_phrases]
    if len(phrases) < top_phrases:
        have = {normalize(p) for p in phrases}
        extra = [p for p in await _enrolled_phrases(db, user_id, language) if normalize(p) not in have]
        phrases += extra[: top_phrases - len(phrases)]

    parts = []
    if names:
        parts.append(", ".join(names) + ".")
    parts.extend(p if p.endswith((".", "?", "!")) else p + "." for p in phrases)
    return " ".join(parts)[:MAX_PROMPT_CHARS]


# Lines Whisper is known to invent from its training data (subtitle credits, video outros).
KNOWN_HALLUCINATIONS = {
    "altyazı m k", "altyazı", "izlediğiniz için teşekkürler", "abone olmayı unutmayın",
    "thanks for watching", "thank you for watching", "subtitles by the amara org community",
    "please subscribe",
}


SENTENCE_END = re.compile(r"(?<=[.?!])\s+")


def _hint_sentences(prompt: str) -> set[str]:
    """The sentences of a hint, normalised, without the list of names ("Zeynep, Ali, Pamuk.")."""
    out = set()
    for chunk in SENTENCE_END.split(prompt):
        pieces = [p.strip() for p in chunk.rstrip(".?!").split(",")]
        if len(pieces) > 1 and all(p[:1].isupper() for p in pieces):
            continue  # the names list: hearing it back word for word is an echo
        out.add(normalize(chunk))
    return out


def _is_hallucination(t: Transcript, prompt: str | None) -> bool:
    """Whisper sometimes repeats the prompt, or invents text, when it hears no clear speech.
    Hearing exactly one of the hint's sentences is not an echo: that is the hint working (the
    user said a phrase they say often, or recorded during enrollment)."""
    text = normalize(t.text)
    if not text or text in KNOWN_HALLUCINATIONS:
        return True
    if prompt and t.prompt_used and len(text) > 8 and text in normalize(prompt) and text not in _hint_sentences(prompt):
        return True
    return (t.no_speech_prob or 0) > 0.8 and (t.avg_logprob or 0) < -1.0


def hint_keyterms(prompt: str | None) -> list[str]:
    """Scribe has no free-text prompt, only a list of key terms: the hint's names and short phrases."""
    if not prompt:
        return []
    terms: list[str] = []
    for chunk in SENTENCE_END.split(prompt):
        pieces = [p.strip() for p in chunk.rstrip(".?!").split(",")]
        if len(pieces) > 1 and all(p[:1].isupper() for p in pieces):
            terms.extend(pieces)  # the names list
        else:
            terms.append(chunk)
    return elevenlabs.keyterms(terms)


async def scribe(wav: Path, language: str | None, prompt: str | None, client: httpx.AsyncClient) -> Transcript:
    """One ElevenLabs Scribe reading, as a Transcript (raises ASRError on failure)."""
    try:
        r = await elevenlabs.transcribe(Path(wav), language, hint_keyterms(prompt), client)
    except elevenlabs.STTError as exc:
        raise ASRError(str(exc)) from exc
    return Transcript(text=r["text"], language=r["language"] or language, avg_logprob=r["avg_logprob"],
                      forced_language=language, engine="elevenlabs")


async def get_candidates(
    wav: Path, language: str | None, prompt: str | None, languages: list[str] | None = None
) -> list[Transcript]:
    """2-3 different Whisper guesses for the same recording, best first, duplicates removed.

    One language: run in parallel with the personal prompt, without it, and with the prompt at
    temperature 0.4 (a slightly more adventurous guess).
    Mixed-language user (language=None, languages=["tr", "en"]): one reading forced to each of
    their languages plus one auto-detected, because auto-detect alone misfires on short words
    (measured: "Hayır" heard as English "Please.", "Merhaba" as Chinese).
    On Groq the third guess uses the turbo model, which has its own rate limit.
    With an ElevenLabs key (and credits), Scribe adds one more reading in parallel: a different
    model family, so when it agrees with Whisper that counts for more than Whisper agreeing with itself.
    """
    alt = ALT_MODEL if _provider()[1] == PROVIDERS["groq"][1] else None
    variants: list[tuple[str | None, float, str | None, str | None]]  # prompt, temperature, model, language
    if language is None and languages:
        variants = [(prompt, 0.0, None, lang) for lang in languages[:2]] + [(None, 0.0, alt, None)]
    elif prompt:
        variants = [(prompt, 0.0, None, language), (None, 0.0, None, language), (prompt, 0.4, alt, language)]
    else:
        variants = [(None, 0.0, None, language), (None, 0.4, alt, language)]
    client = shared_client()
    guesses = [transcribe(wav, lang, p, temp, client=client, model=m) for p, temp, m, lang in variants]
    if elevenlabs.stt_enabled():
        guesses.append(scribe(wav, language, prompt, client))
    results = await asyncio.gather(*guesses, return_exceptions=True)
    errors = [r for r in results if isinstance(r, Exception)]
    for err in errors:
        logger.warning("One speech-to-text guess failed: %s", err)

    candidates: list[Transcript] = []
    by_text: dict[str, Transcript] = {}
    for r in results:
        if isinstance(r, Exception) or _is_hallucination(r, prompt):
            continue
        if languages and r.forced_language is None and r.language not in languages:
            continue  # auto-detect picked a language this user doesn't speak (e.g. Chinese for "Merhaba")
        key = normalize(r.text)
        if key in by_text:
            # Same words from another reading: remember it (it matters which languages agree).
            by_text[key].readings.append(r.reading)
        else:
            r.readings = [r.reading]
            by_text[key] = r
            candidates.append(r)
    if not candidates and len(errors) == len(results):
        raise ASRError(f"All Whisper guesses failed: {errors[0]}")
    return candidates
