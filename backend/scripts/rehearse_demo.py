"""Rehearse the 3-minute demo against a running Echo API (task 6.7: "runs start to finish twice in a row").

Run from backend/ (needs ELEVENLABS_API_KEY locally to make the recordings):

    python -m scripts.rehearse_demo                                   # local API on :8000
    python -m scripts.rehearse_demo --api https://echo-api.onrender.com
    python -m scripts.rehearse_demo --runs 1

Each run follows docs/Echo-Demo-Script.md with a fresh rehearsal user (deleted afterwards):
  1. a clear Turkish sentence  -> right sentence
  2. a clear English sentence  -> right sentence
  3. a slightly unclear one    -> below the threshold, checked, thumbs up
  4. a very unclear one        -> wrong twice, a helper types it, and the NEXT try
                                  (a different take, a new conversation) comes out right
Recordings are made with an ElevenLabs voice and roughened with ffmpeg to imitate unclear speech.
"""

import argparse
import asyncio
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

from app.services import tts
from app.services.audio import ffmpeg_exe
from app.text import similarity

CLEAR_TR = ("Bugün kendimi daha iyi hissediyorum.", "tr")
CLEAR_EN = ("Can you call my daughter, please?", "en")
CHECK = ("Biraz dinlenmek istiyorum.", "tr")
HARD = ("Bugün çok mutluyum.", "tr")

# ffmpeg filters that imitate unclear speech: slower, muffled, crushed, with background noise.
MILD = "[0:a]atempo=0.85,lowpass=f=1400,acrusher=bits=9:mode=log:aa=1[s];anoisesrc=color=pink:amplitude=0.05:d=10:seed={seed}[n];[s][n]amix=inputs=2:duration=first:weights=1 0.5"
HEAVY = "[0:a]atempo={tempo},lowpass=f=600,acrusher=bits=7:mode=log:aa=1[s];anoisesrc=color=pink:amplitude=0.08:d=10:seed={seed}[n];[s][n]amix=inputs=2:duration=first:weights=1 0.7"


def roughen(src: Path, dst: Path, graph: str | None) -> Path:
    cmd = [ffmpeg_exe(), "-loglevel", "error", "-y", "-i", str(src)]
    cmd += ["-filter_complex", graph] if graph else []
    subprocess.run([*cmd, "-ar", "16000", "-ac", "1", str(dst)], check=True)
    return dst


async def make_recordings(folder: Path, voice: str) -> dict[str, Path]:
    clean = {}
    for key, (text, lang) in {"tr": CLEAR_TR, "en": CLEAR_EN, "check": CHECK, "hard": HARD}.items():
        audio, _ = await tts.synthesize(text, lang, voice)
        path = folder / f"{key}.mp3"
        path.write_bytes(audio)
        clean[key] = path
    return {
        "tr": roughen(clean["tr"], folder / "tr.wav", None),
        "en": roughen(clean["en"], folder / "en.wav", None),
        "check": roughen(clean["check"], folder / "check.wav", MILD.format(seed=3)),
        "hard1": roughen(clean["hard"], folder / "hard1.wav", HEAVY.format(tempo=0.75, seed=1)),
        "hard2": roughen(clean["hard"], folder / "hard2.wav", HEAVY.format(tempo=0.72, seed=7)),
    }


class Run:
    def __init__(self, api: httpx.Client, number: int):
        self.api, self.number, self.ok = api, number, True
        self.uid = api.post("/users", json={"name": f"Rehearsal {number}", "main_language": "both", "consent": True}).raise_for_status().json()["user_id"]

    def say(self, path: Path, session: str) -> dict:
        t = time.perf_counter()
        r = self.api.post("/translate", data={"user_id": self.uid, "session_id": session},
                          files={"audio": (path.name, path.read_bytes(), "audio/wav")})
        r.raise_for_status()
        body = r.json()
        body["seconds"] = time.perf_counter() - t
        return body

    def feedback(self, utterance_id: str, verdict: str, final_text: str | None = None) -> dict:
        body = {"utterance_id": utterance_id, "verdict": verdict}
        if final_text:
            body["final_text"] = final_text
        return self.api.post("/feedback", json=body).raise_for_status().json()

    def step(self, name: str, passed: bool, detail: str) -> None:
        self.ok &= passed
        print(f"  {'PASS' if passed else 'FAIL'}  {name:34} {detail}")


def right(result: dict, expected: str) -> bool:
    return similarity(result["sentence"], expected) >= 0.85


def describe(r: dict) -> str:
    return f"{r['sentence']!r}  score {r['score']:.2f} -> {r['action']}  ({r['seconds']:.1f}s)"


def rehearse(api: httpx.Client, rec: dict[str, Path], number: int) -> bool:
    print(f"\nRun {number}")
    run = Run(api, number)
    try:
        session = f"rehearsal-{number}-a"
        r = run.say(rec["tr"], session)
        run.step("1. Turkish sentence", right(r, CLEAR_TR[0]), describe(r))
        r = run.say(rec["en"], session)
        run.step("2. English sentence", right(r, CLEAR_EN[0]), describe(r))

        r = run.say(rec["check"], session)
        checked = r["action"] == "check"
        next_action = run.feedback(r["utterance_id"], "up")["next_action"] if right(r, CHECK[0]) else "-"
        run.step("3. below 0.80 -> check -> thumbs up", checked and right(r, CHECK[0]) and next_action == "speak",
                 f"{describe(r)}, after thumbs up: {next_action}")

        session = f"rehearsal-{number}-b"
        first = run.say(rec["hard1"], session)
        a1 = run.feedback(first["utterance_id"], "down")["next_action"]
        second = run.say(rec["hard1"], session)
        a2 = run.feedback(second["utterance_id"], "down")["next_action"]
        fixed = run.feedback(second["utterance_id"], "down", final_text=HARD[0])["next_action"]
        run.step("4a. wrong twice -> helper types it", a1 == "repeat" and a2 == "helper" and fixed == "speak",
                 f"{first['sentence']!r} then {second['sentence']!r} -> {a1}, {a2}, helper fix -> {fixed}")
        later = run.say(rec["hard2"], f"rehearsal-{number}-c")
        run.step("4b. next try comes out right", right(later, HARD[0]), describe(later))
    finally:
        api.delete(f"/users/{run.uid}/data")  # leave nothing behind
    return run.ok


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--voice", default="will", help="voice that 'speaks' the recordings")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not tts.enabled():
        print("ELEVENLABS_API_KEY is needed to make the rehearsal recordings.")
        return 1

    with httpx.Client(base_url=args.api.rstrip("/"), timeout=120) as api:
        print(f"Waking {args.api} ...")  # a sleeping free Render service takes ~1 minute
        health = api.get("/health").json()
        print(f"  {health}")
        if health.get("db") != "connected":
            print("The API has no database connection. Check MONGODB_URI and the Atlas Network Access list.")
            return 1
        with tempfile.TemporaryDirectory() as tmp:
            rec = await make_recordings(Path(tmp), args.voice)
            results = [rehearse(api, rec, n + 1) for n in range(args.runs)]
    passed = sum(results)
    print(f"\n{passed}/{len(results)} runs passed start to finish")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
