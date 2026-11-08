"""Sound matching: which of the user's past recordings does this new one sound like?

1. Fast pass: cosine similarity of fixed-length fingerprints against every stored recording.
2. Precise pass: dynamic time warping (DTW) on the frame sequences of the best few, which
   lines up the same phrase said slower or faster.
3. Best score per sentence; top 3 distinct sentences are returned.

Measured on clear Turkish/English speech with tempo, pitch and noise changes, the precise
pass picked the right phrase 160/160 times (typical cost: same phrase ~0.04, different ~0.47).
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.services.voiceprint import Voiceprint, compute_from_wav

PRESELECT = 10


@dataclass
class SoundMatch:
    text: str
    score: float  # 0-1, how much the new recording sounds like this sentence
    source: str  # "enrollment" or "utterance"
    ref_id: str
    corrected: bool = False  # a helper typed this sentence for an earlier recording


def dtw_cost(a: np.ndarray, b: np.ndarray) -> float:
    """Average cosine distance along the best time alignment of two frame sequences."""
    a = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
    b = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-9)
    dist = 1.0 - a @ b.T
    n, m = dist.shape
    acc = np.full((n + 1, m + 1), np.inf)
    acc[0, 0] = 0.0
    for i in range(1, n + 1):
        row_prev, row = acc[i - 1], acc[i]
        d = dist[i - 1]
        for j in range(1, m + 1):
            row[j] = d[j - 1] + min(row_prev[j], row_prev[j - 1], row[j - 1])
    return float(acc[n, m] / (n + m))


def cost_to_score(cost: float) -> float:
    """Map a DTW cost to 0-1 (1 = sounds the same). Scale is tunable in settings."""
    return float(np.clip(1.0 - cost / get_settings().sound_match_scale, 0.0, 1.0))


async def load_references(db, user_id: str) -> list[dict]:
    """Every recording of this user that has a fingerprint, with the sentence it means."""
    refs = []
    projection = {"text": 1, "audio_vector": 1, "audio_frames": 1}
    async for d in db.enrollment_samples.find({"user_id": user_id, "audio_vector": {"$exists": True}}, projection):
        refs.append({"id": str(d["_id"]), "text": d["text"], "vector": d["audio_vector"], "frames": d["audio_frames"], "source": "enrollment", "weight": 1.0, "corrected": False})
    # Approved conversation sentences become references too (learning loop, phase 5), and so do
    # rejected attempts relabelled with the sentence the user confirmed afterwards.
    # Examples disputed by a later thumbs-down are left out.
    settings = get_settings()
    query = {
        "user_id": user_id,
        "audio_vector": {"$exists": True},
        "disputed": {"$ne": True},
        "$or": [{"status": "approved"}, {"status": "rejected", "relabelled_from": {"$exists": True}}],
    }
    fields = {**projection, "sentence": 1, "final_text": 1, "was_corrected": 1, "auto_approved": 1, "status": 1}
    async for d in db.utterances.find(query, fields):
        text = d.get("final_text") or d.get("sentence")
        if not text:
            continue
        corrected = d.get("status") == "approved" and bool(d.get("was_corrected"))
        if corrected:
            weight = settings.corrected_match_weight  # helper corrections: the most valuable examples
        elif d.get("auto_approved"):
            weight = settings.silent_match_weight  # nobody checked it: a missed mistake can't push itself to "speak"
        else:
            weight = 1.0
        refs.append({
            "id": str(d["_id"]), "text": text, "vector": d["audio_vector"], "frames": d["audio_frames"],
            "source": "utterance", "weight": weight, "corrected": corrected,
        })
    return refs


def rank(query: Voiceprint, refs: list[dict], top_k: int = 3) -> list[SoundMatch]:
    """Pure ranking step (no I/O) so it can be tested and timed on its own."""
    if not refs:
        return []
    q_vec = np.asarray(query.vector)
    vectors = np.asarray([r["vector"] for r in refs])
    cos = vectors @ q_vec  # all vectors are L2-normalised
    shortlist = np.argsort(-cos)[:PRESELECT]
    q_frames = np.asarray(query.frames)

    best: dict[str, SoundMatch] = {}
    for idx in shortlist:
        ref = refs[idx]
        score = min(1.0, cost_to_score(dtw_cost(q_frames, np.asarray(ref["frames"]))) * ref["weight"])
        key = ref["text"].strip().casefold()
        if key not in best or score > best[key].score:
            best[key] = SoundMatch(text=ref["text"], score=round(score, 4), source=ref["source"], ref_id=ref["id"], corrected=ref.get("corrected", False))
    return sorted(best.values(), key=lambda m: m.score, reverse=True)[:top_k]


async def match_sound(wav: Path, user_id: str, db, top_k: int = 3, query: Voiceprint | None = None) -> list[SoundMatch]:
    """Top `top_k` distinct sentences this recording sounds like, best first."""
    if query is None:
        query = await run_in_threadpool(compute_from_wav, wav)
    refs = await load_references(db, user_id)
    return await run_in_threadpool(rank, query, refs, top_k)


async def load_wrong_guesses(db, user_id: str) -> list[dict]:
    """Recordings whose first guess was wrong, with that wrong guess as the "text"."""
    refs = []
    query = {
        "user_id": user_id,
        "audio_vector": {"$exists": True},
        "$or": [{"status": "rejected"}, {"was_corrected": True}],
    }
    async for d in db.utterances.find(query, {"sentence": 1, "final_text": 1, "audio_vector": 1, "audio_frames": 1}):
        wrong = d.get("sentence")
        if wrong and wrong != d.get("final_text"):
            refs.append({"id": str(d["_id"]), "text": wrong, "vector": d["audio_vector"], "frames": d["audio_frames"], "source": "rejected", "weight": 1.0})
    return refs


async def not_this(query: Voiceprint, user_id: str, db, min_score: float = 0.6, limit: int = 3) -> list[str]:
    """Wrong guesses Echo made before for recordings that sound like this one."""
    refs = await load_wrong_guesses(db, user_id)
    matches = await run_in_threadpool(rank, query, refs, limit)
    return [m.text for m in matches if m.score >= min_score]
