"""The full translate pipeline: one recording in, one clear sentence + a decision out.

audio clean-up -> (Whisper candidates || sound matching || memory look-ups) -> agent -> score
-> action "speak" (score >= the user's threshold) or "check" (ask the user first).
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from bson import ObjectId

from app.agent.run import AgentError, AgentResult, interpret
from app.agent.tools import ToolContext, get_personal_words, get_recent_turns
from app.config import get_settings
from app.services import storage
from app.services.learning import approve_unanswered_spoken
from app.services.asr import ASRError, Transcript, build_prompt, get_candidates
from app.services.scoring import combined_score
from app.services.sound_match import SoundMatch, match_sound, not_this
from app.services.voiceprint import Voiceprint, fingerprint_upload

logger = logging.getLogger("echo.translate")

# Guesses the user rejected this recently in the same conversation are shown as "not this".
REJECTED_WINDOW = timedelta(minutes=3)


@dataclass
class Timer:
    marks: dict[str, float] = field(default_factory=dict)
    _t0: float = field(default_factory=time.perf_counter)
    _last: float = field(default_factory=time.perf_counter)

    def mark(self, step: str) -> None:
        now = time.perf_counter()
        self.marks[step] = round(now - self._last, 3)
        self._last = now

    @property
    def total(self) -> float:
        return round(time.perf_counter() - self._t0, 3)


async def recent_rejections(db, user_id: str, session_id: str) -> list[str]:
    since = datetime.now(UTC) - REJECTED_WINDOW
    cursor = db.utterances.find(
        {"user_id": user_id, "session_id": session_id, "status": "rejected", "created_at": {"$gte": since}},
        {"sentence": 1},
    ).sort("created_at", -1).limit(3)
    return [d["sentence"] async for d in cursor if d.get("sentence")]


async def attempt_number(db, user_id: str, session_id: str) -> int:
    """1 for a new message; 2, 3... when the user is repeating after thumbs-down."""
    attempt = 1
    cursor = db.utterances.find({"user_id": user_id, "session_id": session_id, "speaker": {"$ne": "other"}}).sort("created_at", -1).limit(5)
    async for d in cursor:
        if d.get("status") != "rejected":
            break
        attempt += 1
    return attempt


def _whisper_language(main_language: str) -> str | None:
    """Force the user's language, or auto-detect per recording for mixed-language users."""
    return None if main_language == "both" else main_language


def _output_language(agent_lang: str, candidates: list[Transcript], main_language: str) -> str:
    """tr/en for the voice: the agent's answer, else what Whisper detected, else the user's setting."""
    if agent_lang in ("tr", "en"):
        return agent_lang
    detected = next((c.language for c in candidates if c.language in ("tr", "en")), None)
    if detected:
        return detected
    return main_language if main_language in ("tr", "en") else "tr"


async def translate(db, user: dict, session_id: str, audio_path: str) -> dict:
    """Run the pipeline on an already-saved upload. Returns the API response body."""
    timer = Timer()
    user_id = str(user["_id"])
    main_language = user.get("main_language", "tr")

    # Sentences spoken earlier that never got a thumbs-down are approved (and learned) first.
    await approve_unanswered_spoken(db, user_id)

    ctx = ToolContext(db=db, user_id=user_id, session_id=session_id)
    # Audio clean-up and memory look-ups don't depend on each other: run them together.
    fp, (prompt, words, turns, rejected, attempt) = await asyncio.gather(
        fingerprint_upload(audio_path),  # 16 kHz WAV + voiceprint (raises AudioError)
        asyncio.gather(
            build_prompt(db, user_id),
            get_personal_words(ctx),
            get_recent_turns(ctx),
            recent_rejections(db, user_id, session_id),
            attempt_number(db, user_id, session_id),
        ),
    )
    wav = storage.absolute_path(fp["wav_path"])
    timer.mark("audio+memory")

    async def candidates_task() -> list[Transcript]:
        try:
            return await get_candidates(Path(wav), _whisper_language(main_language), prompt or None)
        except ASRError as exc:
            logger.error("Whisper failed: %s", exc)
            return []

    query = Voiceprint(vector=fp["audio_vector"], frames=fp["audio_frames"])
    candidates, matches, wrong_before = await asyncio.gather(
        candidates_task(),
        match_sound(None, user_id, db, query=query),
        not_this(query, user_id, db),
    )
    # "Not this": guesses rejected in this conversation + wrong guesses for similar-sounding recordings.
    rejected = list(dict.fromkeys([*rejected, *wrong_before]))[:5]
    timer.mark("whisper+sound")

    cand_texts = [c.text for c in candidates]
    match_pairs = [(m.text, m.score) for m in matches]
    try:
        result = await interpret(
            ctx,
            cand_texts,
            match_pairs,
            main_language,
            personal_words=[(w["word"], w["kind"]) for w in words],
            recent_turns=[(t["speaker"], t["text"]) for t in turns],
            rejected=rejected,
        )
    except AgentError as exc:
        # Never stop the user: fall back to the best guess with a low confidence, which
        # always means "check with the user first", never "speak".
        logger.error("Agent failed, using fallback: %s", exc)
        fallback = cand_texts[0] if cand_texts else (matches[0].text if matches else "")
        result = AgentResult(sentence=fallback, confidence=0.3, language="mixed", reason=f"Agent unavailable: {exc}")
    timer.mark("agent")

    score = combined_score(result.confidence, cand_texts, result.sentence, match_pairs)
    threshold = float(user.get("threshold", get_settings().default_threshold))
    action = "speak" if result.sentence and score.score >= threshold else "check"
    language = _output_language(result.language, candidates, main_language)

    utterance_id = ObjectId()
    now = datetime.now(UTC)
    doc = {
        "_id": utterance_id,
        "user_id": user_id,
        "session_id": session_id,
        "speaker": "user",
        "audio_path": audio_path,
        **fp,
        "candidates": [
            {"text": c.text, "language": c.language, "prompt_used": c.prompt_used, "temperature": c.temperature, "avg_logprob": c.avg_logprob}
            for c in candidates
        ],
        "sound_matches": [{"text": m.text, "score": m.score, "source": m.source, "ref_id": m.ref_id} for m in matches],
        "sentence": result.sentence,
        "language": language,
        "agent": {"confidence": result.confidence, "language": result.language, "reason": result.reason, "tool_calls": result.tool_calls},
        "score": score.as_dict(),
        "threshold": threshold,
        "action": action,
        # Spoken sentences are part of the conversation right away; checks wait for a thumbs up.
        "status": "spoken" if action == "speak" else "pending",
        "attempt": attempt,
        "created_at": now,
    }
    timer.mark("score")
    doc["timings"] = {**timer.marks, "total": timer.total}
    await db.utterances.insert_one(doc)
    logger.info(
        "translate user=%s attempt=%d score=%.2f action=%s timings=%s",
        user_id, attempt, score.score, action, doc["timings"],
    )
    return {
        "utterance_id": str(utterance_id),
        "sentence": result.sentence,
        "score": score.score,
        "action": action,
        "language": language,
        "attempt": attempt,
        "reason": result.reason,
        "score_parts": score.as_dict(),
        "timings": doc["timings"],
    }


__all__ = ["translate", "SoundMatch"]
