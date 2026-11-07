"""Synthetic audio for tests (no microphone, no internet)."""

import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from app.services.audio import ffmpeg_exe


def speech_like(seed: int = 0, seconds: float = 1.2, sr: int = 16_000, rate: float = 1.0, noise: float = 0.0) -> np.ndarray:
    """A vowel-like signal whose pitch and formants glide in a pattern set by `seed`.

    Different seeds sound like different "phrases"; `rate` stretches time like speaking
    slower/faster, and `noise` adds background hiss.
    """
    rng = np.random.default_rng(seed)
    n = int(sr * seconds / rate)
    t = np.arange(n) / sr
    knots = rng.uniform(0, 1, size=(4, 6))
    xs = np.linspace(0, 1, 6)
    pos = np.linspace(0, 1, n)
    pitch = 110 + 60 * np.interp(pos, xs, knots[0])
    f1 = 300 + 500 * np.interp(pos, xs, knots[1])
    f2 = 900 + 1400 * np.interp(pos, xs, knots[2])
    amp = 0.3 + 0.7 * np.interp(pos, xs, knots[3])
    phase = 2 * np.pi * np.cumsum(pitch) / sr
    sig = sum(np.sin(k * phase) / k * (np.exp(-((k * pitch - f1) / 200) ** 2) + 0.6 * np.exp(-((k * pitch - f2) / 300) ** 2)) for k in range(1, 30))
    sig = amp * sig / (np.abs(sig).max() + 1e-9) * 0.6
    if noise:
        sig = sig + noise * np.random.default_rng(seed + 1000).standard_normal(n)
    silence = np.zeros(int(0.3 * sr))
    return np.concatenate([silence, sig, silence]).astype(np.float32)


@lru_cache
def speech_like_webm(seed: int = 0) -> bytes:
    """speech_like() encoded as webm/opus, like a browser recording."""
    with tempfile.TemporaryDirectory() as tmp:
        wav, webm = Path(tmp) / "a.wav", Path(tmp) / "a.webm"
        wavfile.write(wav, 16_000, speech_like(seed))
        subprocess.run([ffmpeg_exe(), "-loglevel", "error", "-y", "-i", str(wav), "-c:a", "libopus", str(webm)], check=True)
        return webm.read_bytes()
