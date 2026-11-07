import subprocess
import wave

import numpy as np
import pytest
from scipy.io import wavfile

from app.services.audio import AudioError, SAMPLE_RATE, convert_to_wav_sync, ffmpeg_exe, load_wav, wav_duration


def make_browser_like_webm(tmp_path, silence_s=1.0, tone_s=1.0):
    """48 kHz stereo: silence, a tone, silence; encoded as webm/opus like a browser recording."""
    sr = 48_000
    t = np.arange(int(sr * tone_s)) / sr
    tone = 0.5 * np.sin(2 * np.pi * 440 * t)
    quiet = np.zeros(int(sr * silence_s))
    mono = np.concatenate([quiet, tone, quiet]).astype(np.float32)
    raw = tmp_path / "raw.wav"
    wavfile.write(raw, sr, np.stack([mono, mono], axis=1))
    webm = tmp_path / "rec.webm"
    subprocess.run([ffmpeg_exe(), "-loglevel", "error", "-y", "-i", str(raw), "-c:a", "libopus", str(webm)], check=True)
    return webm


def test_webm_becomes_16k_mono_wav_with_silence_trimmed(tmp_path):
    webm = make_browser_like_webm(tmp_path)
    out = convert_to_wav_sync(webm)
    assert out == tmp_path / "rec.wav"
    with wave.open(str(out), "rb") as w:
        assert w.getframerate() == SAMPLE_RATE
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
    # 3 s in, 1 s tone + 2 x 0.15 s padding out
    assert 1.1 < wav_duration(out) < 1.6
    samples = load_wav(out)
    assert samples.dtype == np.float32 and np.abs(samples).max() > 0.3


def test_no_trim_keeps_full_length(tmp_path):
    out = convert_to_wav_sync(make_browser_like_webm(tmp_path), trim=False)
    assert 2.9 < wav_duration(out) < 3.2


def test_all_silence_is_kept_not_emptied(tmp_path):
    out = convert_to_wav_sync(make_browser_like_webm(tmp_path, silence_s=0.5, tone_s=0.0))
    assert wav_duration(out) > 0.9


def test_wav_input_does_not_overwrite_original(tmp_path):
    src = tmp_path / "a.wav"
    wavfile.write(src, 44_100, (np.random.default_rng(0).standard_normal(44_100) * 3000).astype(np.int16))
    out = convert_to_wav_sync(src)
    assert out.name == "a.clean.wav" and src.exists()


def test_garbage_raises_audio_error(tmp_path):
    bad = tmp_path / "bad.webm"
    bad.write_bytes(b"not audio at all")
    with pytest.raises(AudioError):
        convert_to_wav_sync(bad)
