import numpy as np

from app.services.voiceprint import MAX_FRAMES, N_MFCC, TEMPLATE_FRAMES, compute, mfcc
from tests.audio_utils import speech_like


def cos(a, b):
    a, b = np.array(a), np.array(b)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def test_shapes():
    vp = compute(speech_like(1))
    assert len(vp.vector) == TEMPLATE_FRAMES * N_MFCC
    assert abs(np.linalg.norm(vp.vector) - 1) < 1e-3
    assert 5 <= len(vp.frames) <= MAX_FRAMES and len(vp.frames[0]) == 2 * N_MFCC


def test_same_phrase_closer_than_different_phrase():
    base = compute(speech_like(1)).vector
    same_slower = compute(speech_like(1, rate=0.8, noise=0.01)).vector
    louder = compute(speech_like(1) * 1.8).vector
    different = [compute(speech_like(seed)).vector for seed in (2, 3, 4)]
    # (synthetic tones, not speech: on real speech same-phrase matching is near perfect,
    #  see backend/scripts/eval_asr.py)
    assert cos(base, same_slower) > max(cos(base, d) for d in different) + 0.25
    assert cos(base, louder) > 0.99  # loudness doesn't matter


def test_silence_frames_are_dropped():
    sig = speech_like(3)
    padded = np.concatenate([np.zeros(16000), sig, np.zeros(16000)])
    assert abs(len(mfcc(padded)) - len(mfcc(sig))) < 10


def test_very_short_audio_does_not_crash():
    assert len(compute(np.zeros(100, dtype=np.float32)).vector) == TEMPLATE_FRAMES * N_MFCC
