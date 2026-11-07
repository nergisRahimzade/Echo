import asyncio
import time

import numpy as np

from app.services.sound_match import cost_to_score, dtw_cost, match_sound, rank
from app.services.voiceprint import compute
from tests.audio_utils import speech_like

PHRASES = {1: "Su istiyorum", 2: "Merhaba", 3: "Yorgunum", 4: "Evet", 5: "Hayır"}


def refs_for(seeds):
    out = []
    for seed in seeds:
        vp = compute(speech_like(seed))
        out.append({"id": str(seed), "text": PHRASES[seed], "vector": vp.vector, "frames": vp.frames, "source": "enrollment", "weight": 1.0})
    return out


def test_resaying_an_enrolled_phrase_returns_it_first():
    refs = refs_for(PHRASES)
    for seed in PHRASES:
        again = compute(speech_like(seed, rate=0.85, noise=0.01))  # said a bit slower, some hiss
        matches = rank(again, refs)
        assert matches[0].text == PHRASES[seed]
        assert len(matches) == 3
        assert matches[0].score > matches[1].score


def test_dtw_identical_is_zero_and_score_is_one():
    frames = np.asarray(compute(speech_like(1)).frames)
    assert dtw_cost(frames, frames) < 1e-6
    assert cost_to_score(0.0) == 1.0
    assert cost_to_score(10.0) == 0.0


def test_best_score_per_sentence_and_corrected_weight():
    refs = refs_for([1, 2])
    dup = dict(refs[0], id="dup")  # a second recording of the same sentence
    refs.append(dup)
    matches = rank(compute(speech_like(1)), refs)
    assert [m.text for m in matches].count("Su istiyorum") == 1

    weighted = refs_for([2])[0] | {"weight": 1.5}
    plain = rank(compute(speech_like(2, rate=0.9)), refs_for([2]))[0].score
    boosted = rank(compute(speech_like(2, rate=0.9)), [weighted])[0].score
    assert boosted >= plain and boosted <= 1.0


def test_no_references_returns_empty():
    assert rank(compute(speech_like(1)), []) == []


def test_match_sound_reads_enrollments_and_approved_utterances(fake_db):
    async def run():
        for seed in (1, 2):
            vp = compute(speech_like(seed))
            await fake_db.enrollment_samples.insert_one({"user_id": "u", "text": PHRASES[seed], "audio_vector": vp.vector, "audio_frames": vp.frames})
        vp = compute(speech_like(3))
        await fake_db.utterances.insert_one({"user_id": "u", "status": "approved", "sentence": "x", "final_text": PHRASES[3], "was_corrected": True, "audio_vector": vp.vector, "audio_frames": vp.frames})
        await fake_db.utterances.insert_one({"user_id": "u", "status": "rejected", "sentence": "nope", "audio_vector": vp.vector, "audio_frames": vp.frames})
        await fake_db.enrollment_samples.insert_one({"user_id": "other", "text": "not mine", "audio_vector": vp.vector, "audio_frames": vp.frames})
        return await match_sound(None, "u", fake_db, query=compute(speech_like(3, rate=0.9)))

    matches = asyncio.run(run())
    assert matches[0].text == "Yorgunum" and matches[0].source == "utterance"
    assert {m.text for m in matches} <= {"Su istiyorum", "Merhaba", "Yorgunum"}


def test_fast_enough_for_200_recordings():
    refs = refs_for(PHRASES) * 40
    t0 = time.perf_counter()
    rank(compute(speech_like(1)), refs)
    assert time.perf_counter() - t0 < 1.0
