"""Sound fingerprints: numbers that describe how a recording *sounds*.

Echo compares a new recording with the same person's earlier recordings ("does this sound
like their way of saying X?"). For same-speaker template matching, classic MFCC features
work well and need only numpy, no large neural model on the server.

Each recording gets two forms:
- `audio_vector`: fixed length (TEMPLATE_FRAMES x N_MFCC), L2-normalised -> fast cosine search.
- `audio_frames`: a short frame sequence (<= MAX_FRAMES x 2*N_MFCC, with deltas) -> dynamic
  time warping in match_sound(), which tolerates the same phrase said slower or faster.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.fft import dct

from app.services.audio import SAMPLE_RATE, load_wav

N_MFCC = 13
N_MELS = 40
FRAME = 400  # 25 ms at 16 kHz
HOP = 160  # 10 ms
NFFT = 512
TEMPLATE_FRAMES = 24
MAX_FRAMES = 60
VERSION = 1  # bump when the features change, so stored vectors can be recomputed


@dataclass
class Voiceprint:
    vector: list[float]  # audio_vector
    frames: list[list[float]]  # audio_frames
    version: int = VERSION


@lru_cache
def _mel_filterbank() -> np.ndarray:
    def hz_to_mel(hz):
        return 2595 * np.log10(1 + hz / 700)

    def mel_to_hz(mel):
        return 700 * (10 ** (mel / 2595) - 1)

    mels = np.linspace(hz_to_mel(60), hz_to_mel(SAMPLE_RATE / 2), N_MELS + 2)
    bins = np.floor((NFFT + 1) * mel_to_hz(mels) / SAMPLE_RATE).astype(int)
    fb = np.zeros((N_MELS, NFFT // 2 + 1))
    for i in range(1, N_MELS + 1):
        left, centre, right = bins[i - 1], bins[i], bins[i + 1]
        if centre > left:
            fb[i - 1, left:centre] = (np.arange(left, centre) - left) / (centre - left)
        if right > centre:
            fb[i - 1, centre:right] = (right - np.arange(centre, right)) / (right - centre)
    return fb


def mfcc(samples: np.ndarray) -> np.ndarray:
    """(frames, N_MFCC) MFCCs of speech frames only, normalised per recording (CMVN)."""
    if len(samples) < FRAME:
        samples = np.pad(samples, (0, FRAME - len(samples)))
    emphasized = np.append(samples[0], samples[1:] - 0.97 * samples[:-1])
    n_frames = 1 + (len(emphasized) - FRAME) // HOP
    idx = np.arange(FRAME)[None, :] + HOP * np.arange(n_frames)[:, None]
    frames = emphasized[idx] * np.hamming(FRAME)
    power = np.abs(np.fft.rfft(frames, NFFT)) ** 2 / NFFT
    energy = power.sum(axis=1)

    # Keep frames with speech (drops the padding silence around the recording).
    log_e = 10 * np.log10(energy + 1e-12)
    voiced = log_e > log_e.max() - 35
    if voiced.sum() >= 5:
        power = power[voiced]

    mel = np.log(power @ _mel_filterbank().T + 1e-10)
    # Drop c0 (overall loudness) so a louder or quieter take of the same phrase still matches.
    coeffs = dct(mel, type=2, axis=1, norm="ortho")[:, 1 : N_MFCC + 1]
    std = coeffs.std(axis=0)
    return (coeffs - coeffs.mean(axis=0)) / np.where(std < 1e-6, 1, std)


def _deltas(feats: np.ndarray) -> np.ndarray:
    padded = np.pad(feats, ((1, 1), (0, 0)), mode="edge")
    return (padded[2:] - padded[:-2]) / 2


def _resample(feats: np.ndarray, n: int) -> np.ndarray:
    """Stretch or squeeze a frame sequence to exactly n frames (linear interpolation)."""
    src = np.linspace(0, 1, len(feats))
    dst = np.linspace(0, 1, n)
    return np.stack([np.interp(dst, src, feats[:, d]) for d in range(feats.shape[1])], axis=1)


def _pool(feats: np.ndarray, max_frames: int) -> np.ndarray:
    """Average neighbouring frames so the sequence has at most max_frames frames."""
    if len(feats) <= max_frames:
        return feats
    edges = np.linspace(0, len(feats), max_frames + 1).astype(int)
    return np.stack([feats[a:b].mean(axis=0) for a, b in zip(edges[:-1], edges[1:])])


def compute(samples: np.ndarray) -> Voiceprint:
    feats = mfcc(samples)
    template = _resample(feats, TEMPLATE_FRAMES).ravel()
    vector = template / (np.linalg.norm(template) + 1e-9)
    seq = _pool(np.hstack([feats, _deltas(feats)]), MAX_FRAMES)
    return Voiceprint(
        vector=np.round(vector, 5).tolist(),
        frames=np.round(seq, 3).tolist(),
    )


def compute_from_wav(wav: Path) -> Voiceprint:
    return compute(load_wav(wav))


async def fingerprint_upload(audio_path: str) -> dict:
    """Clean up a saved upload and fingerprint it. Returns fields to store on the document.

    audio_path is relative to the uploads folder; a cleaned 16 kHz WAV is written next to it.
    Raises AudioError if the file is not readable audio.
    """
    from starlette.concurrency import run_in_threadpool

    from app.services import storage
    from app.services.audio import convert_to_wav

    src = storage.absolute_path(audio_path)
    wav = await convert_to_wav(src, src.with_suffix(".wav") if src.suffix != ".wav" else None)
    vp = await run_in_threadpool(compute_from_wav, wav)
    return {
        "wav_path": wav.relative_to(storage.uploads_root()).as_posix(),
        "audio_vector": vp.vector,
        "audio_frames": vp.frames,
        "voiceprint_version": vp.version,
    }
