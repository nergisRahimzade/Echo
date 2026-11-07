"""Audio clean-up: turn any browser recording into the same simple format.

Every recording (webm/opus, mp4, ogg, wav...) becomes 16 kHz mono 16-bit WAV, the format
Whisper and the sound matcher expect, with long silence trimmed from the start and end.
Uses the system ffmpeg if installed, otherwise the copy bundled with `imageio-ffmpeg`.
"""

import shutil
import subprocess
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np
from starlette.concurrency import run_in_threadpool

SAMPLE_RATE = 16_000
# Quieter than this counts as silence. Dysarthric speech can be soft, so keep it low.
SILENCE_DB = -45
# Keep a little silence around the speech so soft first/last sounds are not clipped.
PAD_MS = 150


class AudioError(RuntimeError):
    """The file could not be decoded as audio."""


@lru_cache
def ffmpeg_exe() -> str:
    system = shutil.which("ffmpeg")
    if system:
        return system
    import imageio_ffmpeg  # bundled static build, no install needed

    return imageio_ffmpeg.get_ffmpeg_exe()


def _trim_filter() -> str:
    # silenceremove only trims the start, so: trim, reverse, trim, reverse back. Then pad.
    trim = f"silenceremove=start_periods=1:start_duration=0.05:start_threshold={SILENCE_DB}dB"
    return f"{trim},areverse,{trim},areverse,adelay={PAD_MS},apad=pad_dur={PAD_MS / 1000}"


def _run_ffmpeg(src: Path, dst: Path, trim: bool) -> None:
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-vn"]
    if trim:
        cmd += ["-af", _trim_filter()]
    cmd += ["-ac", "1", "-ar", str(SAMPLE_RATE), "-sample_fmt", "s16", "-f", "wav", str(dst)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise AudioError(f"ffmpeg could not convert {src.name}: {result.stderr.strip()[:300]}")


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def convert_to_wav_sync(src: Path, dst: Path | None = None, trim: bool = True) -> Path:
    """Convert `src` to 16 kHz mono WAV at `dst` (default: same name, .wav). Returns dst."""
    src = Path(src)
    if dst is None:
        dst = src.with_suffix(".wav")
        if dst == src:  # already a .wav: write next to it, don't overwrite the original
            dst = src.with_name(f"{src.stem}.clean.wav")
    dst.parent.mkdir(parents=True, exist_ok=True)
    _run_ffmpeg(src, dst, trim)
    # A recording that is all silence would be trimmed to (almost) nothing: keep it whole instead.
    if trim and wav_duration(dst) <= 2 * PAD_MS / 1000 + 0.05:
        _run_ffmpeg(src, dst, trim=False)
    return dst


async def convert_to_wav(src: Path, dst: Path | None = None, trim: bool = True) -> Path:
    """Async wrapper (ffmpeg runs in a worker thread so the server stays responsive)."""
    return await run_in_threadpool(convert_to_wav_sync, src, dst, trim)


def load_wav(path: Path) -> np.ndarray:
    """Read a 16-bit mono WAV as float32 samples in [-1, 1]."""
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2 or w.getnchannels() != 1:
            raise AudioError(f"{path.name} is not 16-bit mono WAV; convert it first")
        frames = w.readframes(w.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
