"""Is Echo fast enough to talk? Sends recordings to a running server's /translate and times it.

Usage (from backend/, server running):
    python -m scripts.speed_check AUDIO_DIR [--api http://localhost:8000] [--n 6] [--user USER_ID]

Prints each step's time (from the server's own timings) and the end-to-end average.
Target: under 4 seconds per sentence.
"""

import argparse
import statistics
import sys
import time
from pathlib import Path

import httpx

AUDIO = {".wav", ".webm", ".mp4", ".m4a", ".ogg"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio_dir", type=Path)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--user", help="existing user id (default: create a test user)")
    args = ap.parse_args()

    files = sorted(p for p in args.audio_dir.iterdir() if p.suffix.lower() in AUDIO)[: args.n]
    if not files:
        sys.exit(f"No audio files in {args.audio_dir}")
    c = httpx.Client(base_url=args.api, timeout=60)
    uid = args.user or c.post("/users", json={"name": "Speed check", "main_language": "tr", "consent": True}).json()["user_id"]

    rows = []
    for f in files:
        t0 = time.perf_counter()
        r = c.post("/translate", data={"user_id": uid, "session_id": "speed-check"}, files={"audio": (f.name, f.read_bytes(), "audio/wav")})
        wall = time.perf_counter() - t0
        r.raise_for_status()
        t = r.json()["timings"]
        rows.append((f.name, wall, t))
        steps = "  ".join(f"{k} {v:.2f}s" for k, v in t.items() if k != "total")
        print(f"{f.name:<28} end-to-end {wall:.2f}s  | {steps}")

    walls = [w for _, w, _ in rows]
    print(f"\naverage {statistics.mean(walls):.2f}s  median {statistics.median(walls):.2f}s  max {max(walls):.2f}s  (target < 4 s)")
    return 0 if statistics.mean(walls) < 4 else 1


if __name__ == "__main__":
    sys.exit(main())
