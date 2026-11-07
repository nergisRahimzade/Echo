"""How good is Echo's hearing? Runs labelled recordings through Whisper candidates + sound matching.

Usage (from backend/):
    python -m scripts.eval_asr TEST_DIR [--enroll-dir DIR] [--no-asr] [--limit N] [--rpm 20]

Each folder holds audio files plus a labels.json: {"file.wav": {"text": "...", "language": "tr"}}
(backend/scripts/make_test_audio.ps1 creates one). --enroll-dir is the user's enrollment
recordings: sound matching compares every test file against them. No database is needed.
"""

import argparse
import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from app.config import read_env_values

# Use the real keys from .env without requiring every app setting.
for key, value in read_env_values().items():
    if value and (key.endswith("_API_KEY") or key.startswith("MONGODB")):
        os.environ.setdefault(key, value)
os.environ.setdefault("ANTHROPIC_API_KEY", "unused")
os.environ.setdefault("MONGODB_URI", "unused")

from app.services.asr import ASRError, get_candidates  # noqa: E402
from app.services.audio import convert_to_wav_sync  # noqa: E402
from app.services.sound_match import rank  # noqa: E402
from app.services.voiceprint import compute_from_wav  # noqa: E402
from app.text import normalize, word_error_rate  # noqa: E402

AUDIO = {".wav", ".webm", ".mp4", ".m4a", ".ogg", ".mp3"}


def load_labels(folder: Path) -> dict[str, dict]:
    path = folder / "labels.json"
    if not path.exists():
        sys.exit(f"{path} not found: add {{\"file.wav\": {{\"text\": ..., \"language\": ...}}}}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_references(enroll_dir: Path, work: Path) -> list[dict]:
    refs = []
    for name, label in load_labels(enroll_dir).items():
        wav = convert_to_wav_sync(enroll_dir / name, work / f"ref-{Path(name).stem}.wav")
        vp = compute_from_wav(wav)
        refs.append({"id": name, "text": label["text"], "vector": vp.vector, "frames": vp.frames, "source": "enrollment", "weight": 1.0})
    return refs


def cut(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("test_dir", type=Path)
    ap.add_argument("--enroll-dir", type=Path, help="enrollment recordings to match against")
    ap.add_argument("--no-asr", action="store_true", help="skip Whisper (sound matching only)")
    ap.add_argument("--limit", type=int, default=0, help="only the first N files")
    ap.add_argument("--rpm", type=int, default=20, help="Whisper requests/minute allowed (Groq free tier: 20)")
    ap.add_argument("--prompt", default="", help="hint text for Whisper (the user's personal words)")
    args = ap.parse_args()

    labels = load_labels(args.test_dir)
    files = [n for n in labels if Path(n).suffix.lower() in AUDIO]
    if args.limit:
        files = files[: args.limit]
    work = Path(tempfile.mkdtemp(prefix="echo-eval-"))
    refs = build_references(args.enroll_dir, work) if args.enroll_dir else []
    calls_per_file = 3 if args.prompt else 2
    pause = 0 if args.no_asr else max(0.0, 60 * calls_per_file / args.rpm - 1)

    print(f"{len(files)} test files | {len(refs)} enrollment references | Whisper: {'off' if args.no_asr else 'on'}\n")
    header = f"{'file':<24} {'expected':<30} {'best whisper guess':<30} {'WER':>5} {'sound match':<30} {'ok':>3} {'time':>6}"
    print(header)
    print("-" * len(header))

    rows = []
    for i, name in enumerate(files):
        label = labels[name]
        t0 = time.perf_counter()
        wav = convert_to_wav_sync(args.test_dir / name, work / f"t-{Path(name).stem}.wav")
        guess, wer = "", None
        if not args.no_asr:
            try:
                cands = await get_candidates(wav, label.get("language"), args.prompt or None)
                first = cands[0].text if cands else ""  # what Echo would use first
                wer = word_error_rate(label["text"], first)
                guess = first
            except ASRError as exc:
                guess = f"[error: {exc}]"
        top = rank(compute_from_wav(wav), refs, top_k=1) if refs else []
        match = top[0].text if top else ""
        match_ok = bool(top) and normalize(match) == normalize(label["text"])
        elapsed = time.perf_counter() - t0
        rows.append({"wer": wer, "whisper_ok": wer == 0 if wer is not None else None, "match_ok": match_ok if refs else None, "time": elapsed})
        wer_s = f"{wer:.2f}" if wer is not None else "-"
        score = f" ({top[0].score:.2f})" if top else ""
        print(f"{cut(name, 24):<24} {cut(label['text'], 30):<30} {cut(guess, 30):<30} {wer_s:>5} {cut(match + score, 30):<30} {'✓' if match_ok else ('✗' if refs else '-'):>3} {elapsed:>5.1f}s")
        if pause and i < len(files) - 1:
            await asyncio.sleep(pause)

    print("-" * len(header))
    wers = [r["wer"] for r in rows if r["wer"] is not None]
    if wers:
        exact = sum(r["whisper_ok"] for r in rows if r["whisper_ok"] is not None)
        print(f"Whisper: {exact}/{len(wers)} exactly right, average word error rate {sum(wers) / len(wers):.2f}")
    if refs:
        ok = sum(r["match_ok"] for r in rows)
        print(f"Sound matching: right sentence on top {ok}/{len(rows)} ({100 * ok / len(rows):.0f}%)")
    print(f"Average time per file: {sum(r['time'] for r in rows) / len(rows):.2f}s (excluding rate-limit pauses)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
